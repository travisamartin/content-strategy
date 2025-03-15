import os

def build_production_url(abs_file_path, mapping):
    """
    Creates a production URL for a file based on the mapping. Steps:
      1) Convert the path to absolute form with forward slashes.
      2) Find the portion starting at /content/.
      3) If the path is in /content/includes, return None (skip).
      4) Find a matching mapping key (for example, /content/nginx/).
      5) Remove the matched part, strip .md, and remove or adjust _index.
      6) Append leftover path parts to the mapped base URL.
      7) Return "null" if no match is found.
    """
    abs_path = os.path.abspath(abs_file_path).replace(os.sep, '/')

    content_idx = abs_path.find('/content/')
    if content_idx == -1:
        return "null"

    remainder = abs_path[content_idx:]
    if remainder.startswith('/content/includes'):
        return None

    for mapping_key, base_url in mapping.items():
        mk = mapping_key.rstrip('/')
        if remainder.startswith(mk):
            leftover = remainder[len(mk):].lstrip('/')
            if leftover.lower().endswith('.md'):
                leftover = leftover[:-3]
            if leftover == '_index':
                leftover = ''
            elif leftover.endswith('/_index'):
                leftover = leftover.rsplit('/_index', 1)[0]

            if leftover:
                return f"{base_url}/{leftover}/"
            else:
                return f"{base_url}/"
    return "null"