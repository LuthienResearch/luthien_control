for enc in ['utf-8', 'utf-16', 'utf-32', 'ascii']:
    try:
        result = bytes([0xFF]).decode(enc)
        print(f"{enc}: Successfully decoded to {repr(result)}")
    except UnicodeDecodeError as e:
        print(f"{enc}: {e}") 