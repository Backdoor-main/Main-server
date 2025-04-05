"""
Debugging utility for the Backdoor AI Learning Server.

This script helps with diagnosing issues that might occur when running in 
Dropbox-only mode on Render.com.
"""

import os
import sys
import io
import tempfile
import sqlite3
import logging
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

def check_environment():
    """Check the environment variables and platform details."""
    print("\n=== Environment Check ===")
    platform_vars = {
        "RENDER": os.getenv("RENDER", "Not set"),
        "RENDER_DISK_PATH": os.getenv("RENDER_DISK_PATH", "Not set"),
        "KOYEB_DEPLOYMENT": os.getenv("KOYEB_DEPLOYMENT", "Not set"),
        "DROPBOX_ENABLED": os.getenv("DROPBOX_ENABLED", "Not set"),
        "STORAGE_MODE": os.getenv("STORAGE_MODE", "Not set"),
        "BASE_DIR": os.getenv("BASE_DIR", "Not set"),
        "DATA_DIR": os.getenv("DATA_DIR", "Not set"),
        "MODELS_DIR": os.getenv("MODELS_DIR", "Not set"),
        "PYTHON_VERSION": os.getenv("PYTHON_VERSION", "Not set"),
    }
    
    for name, value in platform_vars.items():
        print(f"{name}: {value}")
    
    print("\nPython Info:")
    print(f"Python version: {sys.version}")
    print(f"Python executable: {sys.executable}")
    print(f"Python path: {sys.path}")

def check_directories():
    """Check critical directories for permissions and content."""
    print("\n=== Directory Check ===")
    
    dirs_to_check = [
        "/tmp",
        "/app",
        ".",
        "./data" if os.path.exists("./data") else None,
        "./models" if os.path.exists("./models") else None,
        "./nltk_data" if os.path.exists("./nltk_data") else None,
        os.getenv("DATA_DIR") if os.getenv("DATA_DIR") else None,
        os.getenv("MODELS_DIR") if os.getenv("MODELS_DIR") else None,
        os.getenv("NLTK_DATA_DIR") if os.getenv("NLTK_DATA_DIR") else None,
    ]
    
    dirs_to_check = [d for d in dirs_to_check if d]  # Remove None values
    
    for directory in dirs_to_check:
        print(f"\nChecking {directory}:")
        try:
            if os.path.exists(directory):
                print(f"- Exists: Yes")
                print(f"- Is directory: {os.path.isdir(directory)}")
                print(f"- Readable: {os.access(directory, os.R_OK)}")
                print(f"- Writable: {os.access(directory, os.W_OK)}")
                print(f"- Executable: {os.access(directory, os.X_OK)}")
                
                # Try to list contents
                try:
                    items = os.listdir(directory)
                    print(f"- Contents: {len(items)} items")
                    if len(items) > 0 and len(items) < 10:
                        print(f"  - Files: {', '.join(items)}")
                except Exception as e:
                    print(f"- Error listing contents: {e}")
                
                # Check disk space
                try:
                    stat = os.statvfs(directory)
                    free_space = stat.f_frsize * stat.f_bavail / (1024 * 1024)  # MB
                    total_space = stat.f_frsize * stat.f_blocks / (1024 * 1024)  # MB
                    print(f"- Disk space: {free_space:.1f}MB free / {total_space:.1f}MB total")
                except Exception as e:
                    print(f"- Error checking disk space: {e}")
                
                # Try to write a test file
                test_file = os.path.join(directory, "write_test.txt")
                try:
                    with open(test_file, 'w') as f:
                        f.write(f"Test write at {datetime.now().isoformat()}")
                    print(f"- Write test: Successful")
                    os.remove(test_file)
                    print(f"- Delete test: Successful")
                except Exception as e:
                    print(f"- Write/delete test failed: {e}")
            else:
                print(f"- Exists: No")
        except Exception as e:
            print(f"- Error checking directory: {e}")

def check_memory_database():
    """Test in-memory SQLite database operations."""
    print("\n=== Memory Database Check ===")
    
    try:
        # Create in-memory database
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        
        # Create a test table
        cursor.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, data TEXT)")
        print("- Created test table: OK")
        
        # Insert data
        cursor.execute("INSERT INTO test_table (data) VALUES (?)", ("Test data 1",))
        cursor.execute("INSERT INTO test_table (data) VALUES (?)", ("Test data 2",))
        conn.commit()
        print("- Inserted test data: OK")
        
        # Query data
        cursor.execute("SELECT * FROM test_table")
        rows = cursor.fetchall()
        print(f"- Query result: {len(rows)} rows")
        print(f"- Data: {rows}")
        
        # Dump database to string
        dump = []
        for line in conn.iterdump():
            dump.append(line)
        print(f"- Database dump: {len(dump)} lines")
        if len(dump) > 0:
            print(f"- First line: {dump[0]}")
        
        # Create a second connection and test backup
        conn2 = sqlite3.connect(":memory:")
        conn.backup(conn2)
        cursor2 = conn2.cursor()
        cursor2.execute("SELECT * FROM test_table")
        rows2 = cursor2.fetchall()
        print(f"- Backup test: {len(rows2)} rows copied")
        
        conn.close()
        conn2.close()
        print("- Memory database operations: OK")
    except Exception as e:
        print(f"- Memory database error: {e}")

def check_memory_files():
    """Test in-memory file operations."""
    print("\n=== Memory File Operations Check ===")
    
    try:
        # Create BytesIO
        buffer = io.BytesIO()
        buffer.write(b"Test data for BytesIO buffer")
        buffer.seek(0)
        content = buffer.read().decode('utf-8')
        print(f"- BytesIO read/write: OK")
        print(f"- Content: {content}")
        
        # Test SpooledTemporaryFile
        with tempfile.SpooledTemporaryFile(max_size=1024) as tmp:
            tmp.write(b"Test data for SpooledTemporaryFile")
            tmp.seek(0)
            content = tmp.read().decode('utf-8')
            print(f"- SpooledTemporaryFile read/write: OK")
            print(f"- Content: {content}")
        
        print("- Memory file operations: OK")
    except Exception as e:
        print(f"- Memory file operations error: {e}")

def check_memory_usage():
    """Check memory usage of the system."""
    print("\n=== Memory Usage Check ===")
    
    try:
        import psutil
        virtual_memory = psutil.virtual_memory()
        print(f"- Total: {virtual_memory.total / (1024*1024):.1f} MB")
        print(f"- Available: {virtual_memory.available / (1024*1024):.1f} MB")
        print(f"- Used: {virtual_memory.used / (1024*1024):.1f} MB")
        print(f"- Percent: {virtual_memory.percent}%")
        
        # Check swap
        swap = psutil.swap_memory()
        print(f"- Swap total: {swap.total / (1024*1024):.1f} MB")
        print(f"- Swap used: {swap.used / (1024*1024):.1f} MB")
        print(f"- Swap percent: {swap.percent}%")
        
        # Check process memory
        process = psutil.Process(os.getpid())
        print(f"- Process memory info:")
        mem_info = process.memory_info()
        print(f"  - RSS: {mem_info.rss / (1024*1024):.1f} MB")
        print(f"  - VMS: {mem_info.vms / (1024*1024):.1f} MB")
        
        print("- Memory usage check: OK")
    except ImportError:
        print("- psutil not installed, cannot check memory usage")
    except Exception as e:
        print(f"- Memory usage check error: {e}")

def check_config():
    """Try to load and inspect the application config."""
    print("\n=== Application Config Check ===")
    
    try:
        import config
        
        # Check important config values
        config_vars = {
            "DROPBOX_ENABLED": getattr(config, "DROPBOX_ENABLED", "Not found"),
            "STORAGE_MODE": getattr(config, "STORAGE_MODE", "Not found"),
            "DB_PATH": getattr(config, "DB_PATH", "Not found"),
            "DATA_DIR": getattr(config, "DATA_DIR", "Not found"),
            "MODEL_DIR": getattr(config, "MODEL_DIR", "Not found"),
            "NLTK_DATA_PATH": getattr(config, "NLTK_DATA_PATH", "Not found"),
            "DROPBOX_API_KEY": "Available" if hasattr(config, "DROPBOX_API_KEY") and config.DROPBOX_API_KEY else "Not available",
            "DROPBOX_DB_FILENAME": getattr(config, "DROPBOX_DB_FILENAME", "Not found"),
        }
        
        for name, value in config_vars.items():
            print(f"{name}: {value}")
        
        print("- Config module loaded: OK")
    except ImportError:
        print("- Failed to import config module")
    except Exception as e:
        print(f"- Config check error: {e}")

def check_dropbox_connection():
    """Test the connection to Dropbox and diagnostics folder."""
    print("\n=== Dropbox Connection Check ===")
    
    try:
        import config
        if not getattr(config, "DROPBOX_ENABLED", False):
            print("- Dropbox is not enabled in config")
            return
            
        from utils.dropbox_storage import get_dropbox_storage
        
        try:
            dropbox_storage = get_dropbox_storage()
            print("- Got Dropbox storage instance: OK")
            
            # Check authentication
            account_info = dropbox_storage.dbx.users_get_current_account()
            print(f"- Authentication: OK (account: {account_info.email})")
            
            # Check critical folders
            folders_to_check = [
                dropbox_storage.models_folder_name,  # Models folder
                "temp_files",                         # Temporary files
                "model_extractions",                  # Model extraction output
                "diagnostic_logs",                    # Diagnostic logs
                "ensemble_temp",                      # Ensemble creation temporary files
                "nltk_data",                          # NLTK resources
                "model_validation"                    # Model validation results
            ]
            
            for folder_name in folders_to_check:
                folder_path = f"/{folder_name}"
                try:
                    try:
                        dropbox_storage.dbx.files_get_metadata(folder_path)
                        print(f"- Folder exists: OK ({folder_path})")
                    except Exception:
                        # Try to create folder if it doesn't exist
                        try:
                            dropbox_storage.dbx.files_create_folder_v2(folder_path)
                            print(f"- Created folder: {folder_path}")
                        except Exception as e:
                            print(f"- Error creating folder {folder_path}: {e}")
                except Exception as e:
                    print(f"- Folder check failed for {folder_path}: {e}")
            
            # Try listing models
            try:
                models = dropbox_storage.list_models()
                print(f"- Listed models: OK ({len(models)} models found)")
            except Exception as e:
                print(f"- Model listing failed: {e}")
                
            # Check for base model
            try:
                from learning.trainer_dropbox import check_base_model_in_dropbox
                has_base_model = check_base_model_in_dropbox()
                if has_base_model:
                    print("- Base model check: Found in Dropbox")
                else:
                    print("- Base model check: Not found in Dropbox")
            except Exception as e:
                print(f"- Base model check failed: {e}")
                
            # Check if we can upload a small test file
            try:
                import io
                test_content = f"Dropbox test file created at {datetime.now().isoformat()}"
                test_buffer = io.BytesIO(test_content.encode('utf-8'))
                
                test_result = dropbox_storage.upload_model(
                    test_buffer,
                    "dropbox_test.txt",
                    "diagnostic_logs"
                )
                
                if test_result and test_result.get('success'):
                    print("- Test upload: Success")
                else:
                    print(f"- Test upload failed: {test_result.get('error', 'Unknown error')}")
            except Exception as e:
                print(f"- Test upload failed with error: {e}")
                
            print("- Dropbox connection check: OK")
            
        except Exception as e:
            print(f"- Error getting Dropbox storage: {e}")
            
    except ImportError:
        print("- Failed to import required modules")
    except Exception as e:
        print(f"- Dropbox connection check error: {e}")

def try_memory_db_sync():
    """Test synchronizing a memory DB with Dropbox."""
    print("\n=== Memory DB Dropbox Sync Check ===")
    
    try:
        import config
        if not getattr(config, "DROPBOX_ENABLED", False):
            print("- Dropbox is not enabled in config")
            return
            
        try:
            from utils.memory_db import init_memory_db, sync_memory_db_to_dropbox
            
            # Initialize memory DB
            db = init_memory_db()
            print("- Memory DB initialized: OK")
            
            # Create a test table
            with db:
                db.execute("CREATE TABLE IF NOT EXISTS sync_test (id INTEGER PRIMARY KEY, data TEXT)")
                db.execute("INSERT INTO sync_test (data) VALUES (?)", ("Test data for Dropbox sync",))
                print("- Test data added to memory DB: OK")
            
            # Try to sync to Dropbox
            result = sync_memory_db_to_dropbox()
            if result:
                print("- Sync to Dropbox: OK")
            else:
                print("- Sync to Dropbox: Failed")
            
            print("- Memory DB Dropbox sync check: OK")
            
        except Exception as e:
            print(f"- Error in memory DB sync: {e}")
            
    except ImportError:
        print("- Failed to import required modules")
    except Exception as e:
        print(f"- Memory DB sync check error: {e}")

def save_diagnostics_to_dropbox(diagnostics_output):
    """Save diagnostic output to Dropbox."""
    try:
        import config
        if not getattr(config, "DROPBOX_ENABLED", False):
            print("- Dropbox is not enabled in config, skipping diagnostic upload")
            return False
            
        from utils.dropbox_storage import get_dropbox_storage
        
        try:
            # Get Dropbox storage instance
            dropbox_storage = get_dropbox_storage()
            
            # Create diagnostic logs folder if it doesn't exist
            logs_folder = "diagnostic_logs"
            try:
                dropbox_storage.dbx.files_get_metadata(f"/{logs_folder}")
            except Exception:
                # Create folder if it doesn't exist
                try:
                    dropbox_storage.dbx.files_create_folder_v2(f"/{logs_folder}")
                    print(f"- Created diagnostic logs folder in Dropbox: /{logs_folder}")
                except Exception as e:
                    print(f"- Error creating logs folder: {e}")
                    return False
            
            # Create a timestamped filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"diagnostic_{timestamp}.txt"
            
            # Upload the diagnostics
            import io
            buffer = io.BytesIO(diagnostics_output.encode('utf-8'))
            upload_result = dropbox_storage.upload_model(buffer, filename, logs_folder)
            
            if upload_result and upload_result.get('success'):
                print(f"- Saved diagnostics to Dropbox: {logs_folder}/{filename}")
                
                # Try to get a download URL
                try:
                    model_info = dropbox_storage.get_model_stream(filename, folder=logs_folder)
                    if model_info and model_info.get('success') and 'download_url' in model_info:
                        print(f"- Download URL: {model_info['download_url']}")
                except Exception as e:
                    print(f"- Error getting download URL: {e}")
                
                return True
            else:
                print(f"- Failed to upload diagnostics to Dropbox: {upload_result.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            print(f"- Error uploading diagnostics to Dropbox: {e}")
            return False
            
    except ImportError:
        print("- Failed to import required modules for Dropbox upload")
        return False
    except Exception as e:
        print(f"- Error in save_diagnostics_to_dropbox: {e}")
        return False

def check_base_model():
    """Test the base model and report its status."""
    print("\n=== Base Model Check ===")
    
    try:
        import config
        
        # Check if base model validation is available
        try:
            from utils.model_validator import validate_base_model, get_latest_validation_results
            
            # Check if we have existing validation results
            print("- Checking for existing validation results")
            latest_results = get_latest_validation_results()
            
            if latest_results:
                validation_time = latest_results.get('timestamp', 'unknown')
                print(f"- Found existing validation from: {validation_time}")
                
                # Print validation results summary
                if latest_results.get('success', False):
                    print("- Previous validation status: Passed")
                    
                    # Print metadata
                    metadata = latest_results.get('metadata', {})
                    if metadata:
                        print("- Model metadata:")
                        for key, value in metadata.items():
                            # Don't print very long values
                            if isinstance(value, str) and len(value) > 50:
                                print(f"  - {key}: (long text)")
                            elif isinstance(value, list) and len(value) > 10:
                                print(f"  - {key}: List with {len(value)} items")
                            else:
                                print(f"  - {key}: {value}")
                    
                    # Print structure info
                    structure = latest_results.get('structure', {})
                    if structure:
                        print("- Model structure:")
                        print(f"  - Type: {structure.get('type', 'unknown')}")
                        print(f"  - Inputs: {len(structure.get('inputs', []))}")
                        print(f"  - Outputs: {len(structure.get('outputs', []))}")
                    
                    # Print test results
                    test_results = latest_results.get('test_results', {})
                    if test_results:
                        passed = test_results.get('passed_count', 0)
                        total = test_results.get('total_count', 0)
                        print(f"- Model test results: {passed}/{total} tests passed")
                        
                        # Print sample results
                        samples = test_results.get('samples', [])
                        if samples:
                            print("- Sample predictions:")
                            for i, sample in enumerate(samples[:3]):  # Show up to 3 samples
                                status = "✓" if sample.get('success', False) else "✗"
                                print(f"  - {status} Input: \"{sample.get('input')}\" → \"{sample.get('output')}\" ({sample.get('confidence', 0):.2f})")
                else:
                    print("- Previous validation status: Failed")
                    errors = latest_results.get('errors', [])
                    for error in errors:
                        print(f"  - Error: {error}")
            
            # Run a new validation if requested or if no previous results
            should_revalidate = not latest_results or input("Run new validation? (y/n): ").lower() == 'y'
            
            if should_revalidate:
                print("- Running new base model validation")
                validation_results = validate_base_model()
                
                if validation_results.get('success', False):
                    print("- Validation result: Passed ✓")
                    
                    # Print basic structure info
                    structure = validation_results.get('structure', {})
                    if structure:
                        print(f"- Model type: {structure.get('type', 'unknown')}")
                        inputs = structure.get('inputs', [])
                        outputs = structure.get('outputs', [])
                        print(f"- Model inputs: {len(inputs)}")
                        print(f"- Model outputs: {len(outputs)}")
                    
                    # Print test summary
                    test_results = validation_results.get('test_results', {})
                    if test_results:
                        passed = test_results.get('passed_count', 0)
                        total = test_results.get('total_count', 0)
                        print(f"- Model test results: {passed}/{total} tests passed")
                        
                        # Print sample results
                        samples = test_results.get('samples', [])
                        if samples:
                            print("- Sample predictions:")
                            for i, sample in enumerate(samples):
                                status = "✓" if sample.get('success', False) else "✗"
                                print(f"  - {status} Input: \"{sample.get('input')}\" → \"{sample.get('output')}\" ({sample.get('confidence', 0):.2f})")
                    
                    # Print storage info
                    storage = validation_results.get('storage', {})
                    if storage and storage.get('location') == 'dropbox':
                        print(f"- Validation results saved to: {storage.get('path')}")
                        if 'download_url' in storage:
                            print(f"- Results download URL: {storage.get('download_url')}")
                else:
                    print("- Validation result: Failed ✗")
                    errors = validation_results.get('errors', [])
                    for error in errors:
                        print(f"  - Error: {error}")
        except ImportError:
            print("- Model validator module not available")
            
            # Check directly using CoreML if available
            try:
                import coremltools as ct
                print("- CoreMLTools available, attempting manual model check")
                
                # Get base model
                from utils.model_download import get_base_model_buffer
                model_buffer = get_base_model_buffer()
                
                if model_buffer:
                    print("- Base model found in storage")
                    
                    # Save to temporary file for loading
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix=".mlmodel", delete=False) as tmp:
                        model_buffer.seek(0)
                        tmp.write(model_buffer.read())
                        tmp_path = tmp.name
                    
                    try:
                        # Load model
                        model = ct.models.MLModel(tmp_path)
                        spec = model.get_spec()
                        
                        # Print basic info
                        print(f"- Model type: {spec.WhichOneof('Type')}")
                        print(f"- Model inputs: {len(spec.description.input)}")
                        print(f"- Model outputs: {len(spec.description.output)}")
                        
                        # Check metadata
                        if model.user_defined_metadata:
                            print("- Model metadata:")
                            for key, value in model.user_defined_metadata.items():
                                if len(value) > 50:
                                    print(f"  - {key}: (long text)")
                                else:
                                    print(f"  - {key}: {value}")
                        
                        # Clean up
                        os.unlink(tmp_path)
                    except Exception as e:
                        print(f"- Error loading model: {e}")
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)
                else:
                    print("- Base model not found in storage")
            except ImportError:
                print("- CoreMLTools not available, cannot check model directly")
            except Exception as e:
                print(f"- Error during manual model check: {e}")
    except ImportError:
        print("- Failed to import required modules")
    except Exception as e:
        print(f"- Base model check error: {e}")

def main():
    """Run all diagnostic checks and optionally save to Dropbox."""
    import io
    
    # Capture all output to both print and save to a variable
    output_buffer = io.StringIO()
    
    def tee_print(*args, **kwargs):
        """Print to both stdout and a buffer."""
        print(*args, **kwargs)
        # Also write to our buffer
        print(*args, **kwargs, file=output_buffer)
    
    # Store original print function and replace with our tee_print
    original_print = print
    import builtins
    builtins.print = tee_print
    
    try:
        print("\n======== BACKDOOR AI SERVER DIAGNOSTICS ========")
        print(f"Time: {datetime.now().isoformat()}")
        
        check_environment()
        check_config()
        check_directories()
        check_memory_database()
        check_memory_files()
        check_memory_usage()
        check_dropbox_connection()
        try_memory_db_sync()
        check_base_model()  # Add base model diagnostics
        
        print("\n======== DIAGNOSTICS COMPLETE ========")
        
        # Add Dropbox upload section
        print("\n=== Dropbox Diagnostics Upload ===")
        
        # Get the complete diagnostic output
        diagnostic_output = output_buffer.getvalue()
        
        # Try to save to Dropbox
        save_diagnostics_to_dropbox(diagnostic_output)
    finally:
        # Restore original print function
        builtins.print = original_print

if __name__ == "__main__":
    main()
