import os
from PIL import Image
import argparse
# Given a directory to a set of images, attempts to find duplicates within the image files.
# Method used: difference hash

def dHash(image: Image.ImageFile, hash_size, name:str=None):
    greyed = image.resize((hash_size + 1, hash_size)).convert("L")

    # debug function: if you pass the name into this function, it will save the compressed image prior to hashing
    if name: 
        parts = name.strip('.\\').split('.')
        greyed.save(f"{parts[-2]}_hash.{parts[-1]}")

    hash1 = 0

    for row in range(hash_size):
        for col in range(hash_size):
            left_pixel = greyed.getpixel((col, row))
            right_pixel = greyed.getpixel((col + 1, row))
            bit = left_pixel < right_pixel
            hash1 = hash1 << 1 | bit

    return hash1

# TODO: expand to include GIF and video similarity matching
def is_valid_image(file_name):
    try:
        with Image.open(file_name) as img:
            img.verify()
            return True
    except:
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
            hash = dHash(img, hash_size, name=None) #change the name parameter to name=file to save the hashes 
            if hash not in htf:
                htf[hash] = []
            htf[hash].append(file)
        return htf
    except Exception as e:
        print(f"Error when hashing files: {e}")
        return None

def form_duplicate_groups(hash_to_file_map, max_dist=4):
    if not hash_to_file_map: return {}
    grouped_htf = {}

    for i in hash_to_file_map.keys():
        flg = False
        for j in grouped_htf.keys():
            hamming = bin(i ^ j).count('1')
            if hamming > max_dist:
                continue
            else:
                grouped_htf[j].extend(hash_to_file_map[i])
                flg = True
                break
        if not flg: grouped_htf[i] = hash_to_file_map[i]
    return grouped_htf

def prune_duplicates(grouped_htf):          
    duplicates = [grouped_htf[i] for i in grouped_htf if len(grouped_htf[i]) > 1]
    try:
        cnt = 0
        for dup in duplicates:
            for i in range(len(dup) - 1):
                os.remove(dup[i])
                cnt += 1
        # return whether any images were removed
        return cnt > 0
    except Exception as e:
        print(f"Error when trying to prune duplicates: {e}")
        return False

def deduplicate_images(path, hash_size=8, recursive=False, max_dist=4, delete=False, verbose=False):
    if verbose: print("Reading Files...")
    mapping = read_images_and_get_hash_dict(path, hash_size, recursive)
    if verbose: 
        print(f"Found {len(mapping)} valid image files.")
        print(f"Grouping images by hash...")
    grouped_htf = form_duplicate_groups(mapping, max_dist)
    duplicates = [grouped_htf[i] for i in grouped_htf if len(grouped_htf[i]) > 1]
    if not (grouped_htf and delete): 
        if verbose: print("Delete is disabled or no grouping is present, returning duplicates found")
        return  duplicates #return duplicates found
    if verbose: print("Delete enabled, proceeding with deletion and returning duplicates found")
    delete_res = prune_duplicates(grouped_htf)
    if not delete_res: 
        if verbose: print("No files were deleted.")
    return duplicates

def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('path', default='.', help="Relative path to a folder to start searching for image files from")
    argparser.add_argument('-hs', '--hash_size', metavar=int, default=8, help="Size of hashes to be used for calculating image similarity (bigger sizes are more accurate, but may impact performance for lots of images)")
    argparser.add_argument('-r', '--recursive', action="store_true", default=False, help="Whether to search for image files in sub-folders from the path")
    argparser.add_argument('-m', '--max_dist', metavar=int, default=0, help="Max Hamming Distance to gauge image similarity off the image hashes (setting to 0 will make this look for exact matches only)")
    argparser.add_argument('-d', '--delete', action='store_true', default=False, help='If this flag is enabled, the duplicates found by this program will be deleted, otherwise the duplicates will simply be printed out for manual inspection and deletion')
    argparser.add_argument('-v', '--verbose', action='store_true', default=False, help='If this flag is enabled, enables prints at each stage of program operation using print()')
    args = argparser.parse_args()

    print(deduplicate_images(args.path, int(args.hash_size), args.recursive, int(args.max_dist), args.delete, args.verbose))

if __name__ == "__main__":
    main()