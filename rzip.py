# Reading remote files with fsspec
import fsspec

# URL to the zip file and path to the file within the zip
zip_url = "https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip"
file_path = "dev/dev_databases/codebase_community/codebase_community.sqlite"

url = f"simplecache::zip::{zip_url}::{file_path}"
import pdb

pdb.set_trace()
with fsspec.open(
    url,
    "rb",
    # simplecache={"cache_storage": "/tmp/fsspec_cache"},
) as f:
    # Read the first 100 bytes as an example
    content = f.read(100)
    print(f"Read {len(content)} bytes")
