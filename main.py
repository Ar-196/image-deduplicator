import os
from PIL import Image
import argparse
# Given a directory to a set of images, attempts to find duplicates within the image files.
# Method used: dHash

def dHash(image: Image.ImageFile, hash_size):
    greyed = image.resize((hash_size + 1, hash_size)).convert("L")

    diff = []

    for row in range(hash_size):
        for col in range(hash_size):
            left_pixel = greyed.getpixel((col, row))
            right_pixel = greyed.getpixel((col + 1, row))
            diff.append(left_pixel > right_pixel)

    return sum([2 ** i for (i, v) in enumerate(diff) if v])

def is_valid_image(file_name):
    try:
        with Image.open(file_name) as img:
            img.verify()
            return True
    except Exception as e:
        return False

def read_image_files(path, recursive=False):
    all_files = []

    try:
        # List all entries in the current directory
        for entry in os.listdir(path):
            full_path = os.path.join(path, entry)

            # If it's a directory, recurse into it (if recursion enabled)
            if os.path.isdir(full_path):
                if recursive: all_files += read_image_files(full_path, recursive)
            else:
                all_files.append(full_path)

    except Exception as e:
        print(f"Error when accessing the directory {path}: {e}") 

    return [entry for entry in all_files if is_valid_image(entry)]


def read_images_and_get_hash_dict(path, hash_size, recursive=False):
    try:
        filenames = read_image_files(path, recursive)
    except Exception as e:
        print(f"Error when reading files: {e}")
        exit(1)

    htf = {}

    try:
        for file in filenames:
            img = Image.open(file)
            hash = dHash(img, hash_size)
            if hash not in htf:
                htf[hash] = []
            htf[hash].append(file)
        return htf
    except Exception as e:
        print(f"Error when hashing files: {e}")
        return None

def prune_duplicates(hash_to_file_map):
    if not hash_to_file_map: return False
    duplicates = [hash_to_file_map[i] for i in hash_to_file_map if len(hash_to_file_map[i]) > 1]
    if not duplicates: return False
    try:
        for dup in duplicates:
            for _ in range(len(dup) - 1):
                os.remove(dup.pop())
        return True
    except Exception as e:
        print(f"Error when trying to prune duplicates: {e}")
        return False

def deduplicate_files(path, hash_size, recursive=False):
    mapping = read_images_and_get_hash_dict(path, hash_size, recursive)
    return prune_duplicates(mapping)

def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('path', metavar=str, default='.')
    argparser.add_argument('-hs', '--HASH_SIZE', metavar=int, default=8)
    argparser.add_argument('-r', '--recursive', metavar=bool, default=False)
    args = argparser.parse_args()

    print(deduplicate_files(args.path, args.HASH_SIZE, args.recursive))

if __name__ == "__main__":
    main()