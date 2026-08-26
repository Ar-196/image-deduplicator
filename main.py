import os
from PIL import Image
import argparse
from concurrent.futures.thread import ThreadPoolExecutor

# Given a directory to a set of images, attempts to find duplicates within the image files.
# Method used: difference hash

class ImageDeduplicator:
    threadpool = None

    def __init__(self, max_concurrency:int=8):
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
    def __is_valid_image_file(self, file_name:str):
        try:
            with Image.open(file_name) as img: 
                img.verify()
            return (file_name, Image.open(file_name))
        except:
            return None

    def __read_image_files(self, path:str, recursive=False, sub=False):
        all_files = []
        res = None

        try:
            for entry in os.listdir(path):
                full_path = os.path.join(path, entry)

                if os.path.isdir(full_path):
                    if recursive: all_files += self.__read_image_files(full_path, recursive, sub=True)
                else:
                    all_files.append(full_path)
            if sub: return all_files
            res = [img for img in self.threadpool.map(self.__is_valid_image_file, all_files) if img]
        except Exception as e:
            print(f"Error when accessing the directory {path}: {e}") 

        return res


    def __read_images_and_get_hash_dict(self, path, hash_size, recursive=False):
        try:
            imgfiles = self.__read_image_files(path, recursive)
            if not imgfiles: return {}
        except Exception as e:
            print(f"Error when reading files: {e}")
            exit(1)

        def convertToHashes(f: tuple):
            file, img = f
            hsh = self.__dHash(img, hash_size, name=None) # change the name parameter to name=file to save the hashes 
            w, h = img.size
            img.close()
            return (hsh, w * h, file)

        htf = {}

        try:
            for hsh, size, fname in self.threadpool.map(convertToHashes, imgfiles):
                if hsh not in htf:
                    htf[hsh] = []
                htf[hsh].append((size, fname))
            return htf
        except Exception as e:
            print(f"Error when hashing files: {e}")
            return None

    def __form_duplicate_groups(self, hash_to_file_map, max_dist=4):
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

        # sort grouped hash map by image size and remove size, leaving only file names sorted by size (width * height) within each duplicate group
        for i in grouped_htf:
            grouped_htf[i].sort()
            grouped_htf[i] = [fname for size, fname in grouped_htf[i]]
        return grouped_htf

    def __prune_duplicates(self, grouped_htf):          
        duplicates = [grouped_htf[i] for i in grouped_htf if len(grouped_htf[i]) > 1]
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
        if verbose: print("Reading Files...")
        mapping = self.__read_images_and_get_hash_dict(path, hash_size, recursive)
        if verbose: 
            print(f"Found {len(mapping)} valid image mappings.")
            print(f"Grouping images by hash...")
        grouped_htf = self.__form_duplicate_groups(mapping, max_dist)
        duplicates = [grouped_htf[i] for i in grouped_htf if len(grouped_htf[i]) > 1]
        if not (duplicates and delete): 
            if verbose: 
                if not duplicates: print("No duplicates found")
                else: print("Delete is disabled, returning duplicates found")
            return duplicates # return duplicates found
        if verbose: print("Delete enabled, proceeding with deletion and returning duplicates found")
        delete_res, remaining = self.__prune_duplicates(grouped_htf)
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
    argparser.add_argument('-c', '--concurrency', metavar=int, default=8, help="Max number of threads to use when reading and hashing files.")
    args = argparser.parse_args()
    
    deduplicator = ImageDeduplicator(int(args.concurrency))
    res = deduplicator.deduplicate_images(args.path, int(args.hash_size), args.recursive, int(args.max_dist), args.delete, args.verbose)

    out = open("duplicates.txt", "w")
    for dupe in res:
        out.write(f'[{", ".join(dupe)}]\n')
        

if __name__ == "__main__":
    main()