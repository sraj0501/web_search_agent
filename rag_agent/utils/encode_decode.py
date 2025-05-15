import chardet

def detect_file_encoding(fname):
    with open(fname, 'rb') as file:
        raw_data = file.read(100000)

    result = chardet.detect(raw_data)

    return result["encoding"], result["confidence"]