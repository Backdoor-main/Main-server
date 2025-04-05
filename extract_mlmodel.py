import os
import sys
import io
from pathlib import Path
import shutil
import tempfile
import logging
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import coremltools, handle if not installed
try:
    import coremltools as ct
except ImportError:
    logger.error("coremltools is not installed. Please install it with 'pip install coremltools'")
    sys.exit(1)

# Import config for Dropbox integration
try:
    import config
    DROPBOX_ENABLED = config.DROPBOX_ENABLED
except ImportError:
    DROPBOX_ENABLED = False
    logger.warning("Could not import config, assuming Dropbox is disabled")

def extract_mlmodel_info(mlmodel_path, output_dir=None, dropbox_folder="model_extractions"):
    """
    Extract information from the .mlmodel file.
    
    Args:
        mlmodel_path: Path to the CoreML model file
        output_dir: Local directory for output (if None, use temp dir)
        dropbox_folder: Folder in Dropbox to store extracted info
    
    Returns:
        Dict with extraction results including Dropbox URLs
    """
    # Create a timestamp for this extraction
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    extraction_id = f"extraction_{timestamp}"
    
    # Set up local output directory if needed
    if output_dir is None:
        output_dir = tempfile.mkdtemp()
    else:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Extracting model info from {mlmodel_path} to {output_dir}")
    
    if not os.path.exists(mlmodel_path):
        logger.error(f"File {mlmodel_path} not found")
        return {"success": False, "error": f"Model file not found: {mlmodel_path}"}

    extraction_results = {
        "success": True,
        "model_path": mlmodel_path,
        "extraction_id": extraction_id,
        "timestamp": timestamp,
        "local_dir": output_dir,
        "files": [],
        "dropbox_urls": {}
    }
    
    try:
        # Load the Core ML model
        model = ct.models.MLModel(mlmodel_path)
        
        # Extract model specification
        spec = model.get_spec()
        
        # Create files in memory for Dropbox upload or save locally
        file_contents = {}
        
        # Save the full specification
        spec_text = str(spec)
        file_contents["model_spec.txt"] = spec_text
        
        # Extract inputs
        inputs_text = ""
        for input in spec.description.input:
            inputs_text += f"Input Name: {input.name}\n"
            inputs_text += f"Type: {input.type}\n\n"
        file_contents["inputs.txt"] = inputs_text
        
        # Extract outputs
        outputs_text = ""
        for output in spec.description.output:
            outputs_text += f"Output Name: {output.name}\n"
            outputs_text += f"Type: {output.type}\n\n"
        file_contents["outputs.txt"] = outputs_text
        
        # If it's a neural network, extract layer info
        if spec.WhichOneof('Type') == 'neuralNetwork':
            layers_text = ""
            for i, layer in enumerate(spec.neuralNetwork.layers):
                layers_text += f"Layer {i}: {layer.name}\n"
                layers_text += f"Type: {layer.WhichOneof('layer')}\n\n"
            file_contents["layers.txt"] = layers_text
        
        # Also create a summary JSON file
        summary = {
            "model_type": spec.WhichOneof('Type'),
            "specification_version": str(spec.specificationVersion),
            "input_count": len(spec.description.input),
            "output_count": len(spec.description.output),
            "layers": len(spec.neuralNetwork.layers) if spec.WhichOneof('Type') == 'neuralNetwork' else 0,
            "extraction_date": datetime.now().isoformat()
        }
        
        # Add user-defined metadata if available
        if model.user_defined_metadata:
            summary["metadata"] = {k: v for k, v in model.user_defined_metadata.items()}
            
        file_contents["summary.json"] = json.dumps(summary, indent=2)
        
        # Write files locally first
        for filename, content in file_contents.items():
            filepath = os.path.join(output_dir, filename)
            with open(filepath, "w") as f:
                f.write(content)
            extraction_results["files"].append(filepath)
        
        # Upload to Dropbox if enabled
        if DROPBOX_ENABLED:
            try:
                from utils.dropbox_storage import get_dropbox_storage
                dropbox_storage = get_dropbox_storage()
                
                # Make sure extraction folder exists
                try:
                    folder_path = f"/{dropbox_folder}"
                    try:
                        dropbox_storage.dbx.files_get_metadata(folder_path)
                    except Exception:
                        # Create folder if it doesn't exist
                        logger.info(f"Creating Dropbox folder: {folder_path}")
                        dropbox_storage.dbx.files_create_folder_v2(folder_path)
                        
                    # Create subfolder for this extraction
                    subfolder_path = f"{folder_path}/{extraction_id}"
                    try:
                        dropbox_storage.dbx.files_create_folder_v2(subfolder_path)
                        logger.info(f"Created extraction subfolder: {subfolder_path}")
                    except Exception as e:
                        logger.warning(f"Error creating extraction subfolder: {e}")
                except Exception as e:
                    logger.error(f"Error checking/creating Dropbox folders: {e}")
                
                # Upload each file
                for filename, content in file_contents.items():
                    buffer = io.BytesIO(content.encode('utf-8'))
                    dropbox_path = f"{extraction_id}/{filename}"
                    result = dropbox_storage.upload_model(
                        buffer,
                        filename,
                        f"{dropbox_folder}/{extraction_id}"
                    )
                    
                    if result and result.get('success'):
                        # Try to get a download URL
                        try:
                            model_info = dropbox_storage.get_model_stream(
                                filename,
                                folder=f"{dropbox_folder}/{extraction_id}"
                            )
                            if model_info and model_info.get('success') and 'download_url' in model_info:
                                extraction_results["dropbox_urls"][filename] = model_info['download_url']
                        except Exception as e:
                            logger.warning(f"Error getting download URL for {filename}: {e}")
                
                logger.info(f"Uploaded model extraction files to Dropbox: {dropbox_folder}/{extraction_id}")
                extraction_results["dropbox_folder"] = f"{dropbox_folder}/{extraction_id}"
                
            except Exception as e:
                logger.error(f"Error uploading to Dropbox: {e}")
        
        logger.info(f"Extracted model information to {output_dir} and Dropbox")
        return extraction_results
        
    except Exception as e:
        logger.error(f"Error processing .mlmodel file: {e}")
        
        # As a fallback, copy the original file
        try:
            fallback_path = os.path.join(output_dir, os.path.basename(mlmodel_path))
            shutil.copy(mlmodel_path, fallback_path)
            extraction_results["files"].append(fallback_path)
            extraction_results["fallback"] = True
            
            # Try to upload to Dropbox
            if DROPBOX_ENABLED:
                try:
                    from utils.dropbox_storage import get_dropbox_storage
                    dropbox_storage = get_dropbox_storage()
                    
                    with open(fallback_path, 'rb') as f:
                        result = dropbox_storage.upload_model(
                            f,
                            os.path.basename(mlmodel_path),
                            f"{dropbox_folder}/{extraction_id}"
                        )
                except Exception as e2:
                    logger.error(f"Error uploading fallback file to Dropbox: {e2}")
        except Exception as copy_err:
            logger.error(f"Error copying fallback file: {copy_err}")
            extraction_results["success"] = False
            extraction_results["error"] = str(e)
        
        return extraction_results

def create_zip_from_directory(directory, zip_name, upload_to_dropbox=True, dropbox_folder="model_extractions"):
    """
    Create a ZIP file from a directory and optionally upload to Dropbox.
    
    Args:
        directory: Directory to zip
        zip_name: Name for the zip file
        upload_to_dropbox: Whether to upload to Dropbox
        dropbox_folder: Folder in Dropbox to store the zip
        
    Returns:
        Dict with zip information
    """
    local_zip_path = shutil.make_archive(zip_name.replace('.zip', ''), 'zip', directory)
    
    result = {
        "success": True,
        "local_path": local_zip_path,
        "size": os.path.getsize(local_zip_path) if os.path.exists(local_zip_path) else 0
    }
    
    # Upload to Dropbox if enabled
    if upload_to_dropbox and DROPBOX_ENABLED:
        try:
            from utils.dropbox_storage import get_dropbox_storage
            dropbox_storage = get_dropbox_storage()
            
            # Upload ZIP file
            with open(local_zip_path, 'rb') as f:
                upload_result = dropbox_storage.upload_model(
                    f,
                    os.path.basename(local_zip_path),
                    dropbox_folder
                )
                
                if upload_result and upload_result.get('success'):
                    result["dropbox_path"] = upload_result.get('path')
                    
                    # Try to get a download URL
                    try:
                        model_info = dropbox_storage.get_model_stream(
                            os.path.basename(local_zip_path),
                            folder=dropbox_folder
                        )
                        if model_info and model_info.get('success') and 'download_url' in model_info:
                            result["download_url"] = model_info['download_url']
                    except Exception as e:
                        logger.warning(f"Error getting download URL for ZIP: {e}")
                    
                    logger.info(f"Uploaded ZIP file to Dropbox: {upload_result.get('path')}")
                else:
                    logger.warning(f"Failed to upload ZIP to Dropbox: {upload_result.get('error', 'Unknown error')}")
                    
        except Exception as e:
            logger.error(f"Error uploading ZIP to Dropbox: {e}")
    
    return result

def main():
    # Default paths - can be overridden with command line arguments
    ML_MODEL_PATH = "model/coreml_model.mlmodel"
    OUTPUT_DIR = "extracted_model"
    ZIP_NAME = "model_contents.zip"
    DROPBOX_FOLDER = "model_extractions"
    
    # Allow overriding defaults with command line arguments
    if len(sys.argv) > 1:
        ML_MODEL_PATH = sys.argv[1]
    if len(sys.argv) > 2:
        OUTPUT_DIR = sys.argv[2]
    
    # Extract model information
    extraction_results = extract_mlmodel_info(ML_MODEL_PATH, OUTPUT_DIR, DROPBOX_FOLDER)
    
    if extraction_results["success"]:
        # Create and upload a ZIP of the extracted contents
        zip_result = create_zip_from_directory(OUTPUT_DIR, ZIP_NAME, True, DROPBOX_FOLDER)
        
        # Print results
        print("\nModel extraction completed successfully!")
        print(f"Extracted to local directory: {OUTPUT_DIR}")
        print(f"Created ZIP file: {zip_result['local_path']}")
        
        if "dropbox_folder" in extraction_results:
            print(f"\nFiles uploaded to Dropbox folder: {extraction_results['dropbox_folder']}")
            
            if "download_url" in zip_result:
                print(f"\nZIP download URL: {zip_result['download_url']}")
            
            # Print URLs for individual files if available
            if extraction_results["dropbox_urls"]:
                print("\nIndividual file download URLs:")
                for filename, url in extraction_results["dropbox_urls"].items():
                    print(f"- {filename}: {url}")
    else:
        print(f"\nModel extraction failed: {extraction_results.get('error', 'Unknown error')}")

if __name__ == "__main__":
    main()
