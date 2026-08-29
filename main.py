import os
from PIL import Image
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Given a directory to a set of images, attempts to find duplicates within the image files.
# Method used: difference hash

class ImageDeduplicator:
    threadpool = None

    def __init__(self, max_concurrency:int=4):
        self.threadpool = ThreadPoolExecutor(max_workers=max_concurrency)

    def __dHash(self, image, hash_size:int, name:str=None):
        if image.mode != "RGBA":
            image = image.convert("RGBA")

        greyed = image.resize((hash_size + 1, hash_size)).convert("L")

        # debug feature: if you pass the name into this function, it will save the compressed image prior to hashing
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
    def __hash_if_valid_image(self, file_name:str, hash_size:int=8):
        try:
            with Image.open(file_name) as img: 
                img.verify()

            with Image.open(file_name) as img:
                w, h = img.size
                hsh = self.__dHash(img, hash_size)

            return (hsh, w * h, file_name)
        except:
            return None

    def __read_image_files_and_hash(self, path:str, recursive=False, hash_size=8, sub=False):
        all_files = []
        res = None

        try:
            for entry in os.listdir(path):
                full_path = os.path.join(path, entry)

                if os.path.isdir(full_path):
                    if recursive: all_files += self.__read_image_files_and_hash(full_path, recursive, hash_size, sub=True)
                else:
                    all_files.append(full_path)
            if sub: return all_files

            futures = [self.threadpool.submit(self.__hash_if_valid_image, file) for file in all_files]
            res = []
            for future in as_completed(futures):
                try:
                    completed_res = future.result()
                except Exception as e:
                    print(f"Task generated an exception: {e}")
                else:
                    if completed_res: res.append(completed_res)

        except Exception as e:
            print(f"Error when accessing the directory {path}: {e}") 

        return res


    def __read_images_and_get_hash_dict(self, path, hash_size, recursive=False):
        try:
            imgfiles = self.__read_image_files_and_hash(path, recursive, hash_size)
            if not imgfiles: return {}
        except Exception as e:
            print(f"Error when reading files: {e}")
            exit(1)

        htf = {}

        try:
            for hsh, size, fname in imgfiles:
                if hsh not in htf:
                    htf[hsh] = []
                htf[hsh].append((size, fname))
            return htf
        except Exception as e:
            print(f"Error when hashing files: {e}")
            return None

    def __form_duplicate_groups(self, hash_to_file_map, max_dist=4):
        if not hash_to_file_map: return []
        hashes = list(hash_to_file_map.keys())

        parent = {h: h for h in hashes}

        def find(h):
            if parent[h] != h:
                parent[h] = find(parent[h])
            return parent[h]

        def union(a, b):
            root_a = find(a)
            root_b = find(b)

            if root_a != root_b:
                parent[root_b] = root_a

        for i, h1 in enumerate(hashes):
            for h2 in hashes[i + 1:]:
                hamming = bin(h1 ^ h2).count('1')
                if hamming <= max_dist:
                    union(h1, h2)

        hash_groups = {}
        for h in hashes:
            root = find(h)
            hash_groups.setdefault(root, []).append(h)

        file_groups = []

        for hash_group in hash_groups.values():
            files = []

            for h in hash_group:
                files.extend(hash_to_file_map[h])

            file_groups.append(files)

        for i in range(len(file_groups)):
            file_groups[i].sort()
            file_groups[i] = [fname for size, fname in file_groups[i]]

        return file_groups

    def __prune_duplicates(self, duplicates:list):
        try:
            cnt = 0
            for dup in duplicates:
                for i in range(len(dup) - 1):
                    os.remove(dup.pop(0))
                    cnt += 1
                
            # return number of images were removed, as well as images that remain
            return (cnt, duplicates)
        except Exception as e:
            print(f"Error when trying to prune duplicates: {e}")
            return (cnt, duplicates)

    def deduplicate_images(self, path, hash_size=8, recursive=False, max_dist=4, delete=False, verbose=False):
        start_time = datetime.now()
        if verbose: 
            print("Reading Files...")

        mapping = self.__read_images_and_get_hash_dict(path, hash_size, recursive)
        if verbose: 
            print(f"Found {len(mapping)} valid image mappings (time taken: {str(datetime.now() - start_time).split('.')[0]})")
            print(f"Grouping images by hash...")
        grouped_htf = self.__form_duplicate_groups(mapping, max_dist)
        duplicates = [group for group in grouped_htf if len(group) > 1]
        if not (duplicates and delete): 
            if verbose: 
                if not duplicates: print("No duplicates found")
                else: print("Delete is disabled, returning duplicates found")
            return duplicates # return duplicates found
        if verbose: print("Delete enabled, proceeding with deletion and returning duplicates found")
        delete_res, remaining = self.__prune_duplicates(duplicates)
        if verbose: print(f"{delete_res} files were deleted.")
        return remaining

def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('path', default='.', help="Relative path to a directory to start searching for image files from")
    argparser.add_argument('-hs', '--hash_size', metavar=int, default=8, help="Size of hashes to be used for calculating image similarity (bigger sizes allow for smaller patterns to be detected in the hash, but may impact performance and memory for lots of images)")
    argparser.add_argument('-r', '--recursive', action="store_true", default=False, help="Whether to search for image files in sub-folders from the path")
    argparser.add_argument('-m', '--max_dist', metavar=int, default=0, help="Max Hamming Distance to gauge image similarity off the image hashes (setting to 0 will make this look for exact matches only. Recommended value here is ~25%% of hash_size^2 for similar images, and ~12.5%% of hash_size^2 for more exact duplicate matching while still accounting for minor alterations and resolution differences)")
    argparser.add_argument('-d', '--delete', action='store_true', default=False, help='If this flag is enabled, the duplicates found by this program will be deleted, otherwise the duplicates will simply be printed out for manual inspection and deletion.')
    argparser.add_argument('-v', '--verbose', action='store_true', default=False, help='If this flag is enabled, enables prints at each stage of program operation using print()')
    argparser.add_argument('-c', '--concurrency', metavar=int, default=4, help="Max number of threads to use when reading and hashing files.")
    args = argparser.parse_args()
    
    deduplicator = ImageDeduplicator(int(args.concurrency))
    res = deduplicator.deduplicate_images(args.path, int(args.hash_size), args.recursive, int(args.max_dist), args.delete, args.verbose)

    out = open("duplicates.txt", "w")
    for dupe in res:
        out.write(f'[{", ".join(dupe)}]\n')
        

if __name__ == "__main__":
    main()