from io import TextIOWrapper
from typing import Any, Callable, Iterable, List, Optional, Tuple
from urllib import request
from urllib.parse import urlparse, parse_qs
import os.path
import os

def read_input(prompt: str, default: str) -> str:
    value = input(prompt.format(default))
    if not value:
        return default
    return value

def read_confirm(prompt: str, default: bool = False) -> bool:
    value = input(prompt)
    if not value:
        return default
    return value.lower() in ('y', 'yes')

def template(ifile: TextIOWrapper, ofile: TextIOWrapper, **kwargs) -> None:
    """
    Replace the template variables in the input file and write the result to the output file.
    """
    for line in ifile:
        new_line = None
        last = 0
        i = line.find('%', last)
        while i >= 0:
            j = line.find('%', i + 1)
            if j <= i:
                raise ValueError('Invalid template variable: empty')
            key = line[i+1:j]
            value = kwargs.get(key)
            if value is None:
                raise ValueError('Invalid template variable: {}'.format(key))
            if new_line is None:
                new_line = line[last:i]
            else:
                new_line += line[last:i]
            new_line += value
            last = j + 1
            i = line.find('%', last)
        if new_line is not None:
            new_line += line[last:]
            line = new_line
        ofile.write(line)

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.114 Safari/537.36 Edg/103.0.1264.62'

def download(url: str, timeout: int = 5000) -> Tuple[bytes, Optional[str]]:
    """
    Download the content from the URL and return bytes and the filename if exist.
    Tries Content-Disposition first, then falls back to URL path extraction.
    """
    filename: Optional[str] = None
    req = request.Request(url)
    req.add_header('User-Agent', USER_AGENT)
    resp = request.urlopen(req, timeout=timeout/1000.0)

    content = resp.read()
    
    # Try to extract filename from Content-Disposition header
    content_disposition = resp.headers.get('Content-Disposition', '')
    if 'filename=' in content_disposition:
        filename = content_disposition.split('filename=')[1].strip('"\'')
    
    # Fallback: extract from URL path
    if not filename:
        parsed_url = urlparse(url)
        path = parsed_url.path
        if path:
            filename = os.path.basename(path)
            # Remove query strings if present in filename
            if '?' in filename:
                filename = filename.split('?')[0]
        # If still no filename or it's empty, try query parameters
        if not filename:
            query_params = parse_qs(parsed_url.query)
            # Check common parameter names
            for key in ['file', 'name', 'filename', 'download']:
                if key in query_params:
                    filename = query_params[key][0]
                    break
    
    return content, filename


def download_file(url: str, folder: str, default_file_name: str, timeout: int = 5000) -> str:
    """
    Download a file directly to a folder without loading entire content into memory.
    Streams the file in chunks to avoid memory issues with large files.
    
    Args:
        url: The URL to download from
        folder: The destination folder path
        default_file_name: Default filename if extraction from URL fails
        timeout: Timeout in milliseconds (default: 5000ms)
    
    Returns:
        The full path to the downloaded file
    """
    # Ensure folder exists
    os.makedirs(folder, exist_ok=True)
    
    filename: Optional[str] = None
    req = request.Request(url)
    req.add_header('User-Agent', USER_AGENT)
    resp = request.urlopen(req, timeout=timeout/1000.0)
    
    # Try to extract filename from Content-Disposition header
    content_disposition = resp.headers.get('Content-Disposition', '')
    if 'filename=' in content_disposition:
        filename = content_disposition.split('filename=')[1].strip('"\'')
    
    # Fallback: extract from URL path
    if not filename:
        parsed_url = urlparse(url)
        path = parsed_url.path
        if path:
            filename = os.path.basename(path)
            # Remove query strings if present in filename
            if '?' in filename:
                filename = filename.split('?')[0]
        # If still no filename or it's empty, try query parameters
        if not filename:
            query_params = parse_qs(parsed_url.query)
            # Check common parameter names
            for key in ['file', 'name', 'filename', 'download']:
                if key in query_params:
                    filename = query_params[key][0]
                    break
    
    # Use default if still no filename
    if not filename:
        filename = default_file_name
    
    file_path = os.path.join(folder, filename)
    
    # Download file in chunks to avoid memory issues
    chunk_size = 8192  # 8KB chunks
    with open(file_path, 'wb') as f:
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
    
    return file_path


def insert_in_list(original: Optional[List[Any]], locate: Callable[[Any], bool], items: Iterable[Any]) -> List[Any]:
    if not original or len(original) == 0:
        return list(items)
    result: List[Any] = []
    inserted = False
    for v in original:
        if locate(v):
            if inserted:
                raise ValueError('multiple insert location match found')
            inserted = True
            for item in items:
                result.append(item)
        else:
            result.append(v)
    if not inserted:
        for item in items:
            result.append(item)
    return result

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print('Usage: {} <input> <output> [key=value ...]'.format(sys.argv[0]))
        sys.exit(1)
    ifile_name = sys.argv[1]
    ofile_name = sys.argv[2]
    variables = dict(arg.split('=') for arg in sys.argv[3:])
    print('variables:', variables)
    with open(ifile_name, 'r') as ifile:
        with open(ofile_name, 'w') as ofile:
            template(ifile, ofile, **variables)