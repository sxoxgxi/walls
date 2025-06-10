import json
import hashlib
from datetime import datetime
from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS
import argparse
from collections import Counter
import colorsys

class WallpaperMetadataExtractor:
    def __init__(self, wallpaper_folder, json_file="metadata.json"):
        self.wallpaper_folder = Path(wallpaper_folder)
        self.json_file = Path(json_file)
        self.metadata_db = self.load_existing_metadata()
        
    def load_existing_metadata(self):
        """Load existing metadata from JSON file if it exists"""
        if self.json_file.exists():
            try:
                with open(self.json_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                print(f"Warning: Could not load existing metadata from {self.json_file}")
                return {}
        return {}
    
    def get_file_hash(self, file_path):
        """Generate MD5 hash of file for duplicate detection"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            print(f"Error hashing file {file_path}: {e}")
            return None
    
    def extract_exif_data(self, image):
        """Extract EXIF data from image"""
        exif_data = {}
        try:
            if hasattr(image, '_getexif') and image._getexif() is not None:
                exif = image._getexif()
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    exif_data[tag] = str(value)
        except Exception as e:
            print(f"Error extracting EXIF data: {e}")
        return exif_data
    
    def rgb_to_hex(self, rgb):
        """Convert RGB tuple to hex color code"""
        return "#{:02x}{:02x}{:02x}".format(rgb[0], rgb[1], rgb[2])
    
    def get_color_name(self, rgb):
        """Get approximate color name from RGB values"""
        r, g, b = rgb
        
        h, s, v = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
        h = h * 360
        s = s * 100
        v = v * 100
        
        if v < 20:
            return "black"
        elif v > 90 and s < 10:
            return "white"
        elif s < 15:
            if v < 40:
                return "dark_gray"
            elif v > 70:
                return "light_gray"
            else:
                return "gray"
        else:
            if h < 15 or h >= 345:
                return "red"
            elif 15 <= h < 45:
                return "orange"
            elif 45 <= h < 75:
                return "yellow"
            elif 75 <= h < 150:
                return "green"
            elif 150 <= h < 210:
                return "cyan"
            elif 210 <= h < 270:
                return "blue"
            elif 270 <= h < 315:
                return "purple"
            else:
                return "pink"
    
    def extract_dominant_colors(self, image, num_colors=5):
        """Extract dominant colors from image"""
        try:
            img_small = image.copy()
            img_small.thumbnail((150, 150))
            
            if img_small.mode != 'RGB':
                img_small = img_small.convert('RGB')
            
            pixels = list(img_small.getdata())
            
            color_counts = Counter(pixels)
            
            most_common = color_counts.most_common(num_colors)
            
            dominant_colors = []
            for color, count in most_common:
                percentage = (count / len(pixels)) * 100
                color_info = {
                    "rgb": color,
                    "hex": self.rgb_to_hex(color),
                    "name": self.get_color_name(color),
                    "percentage": round(percentage, 2)
                }
                dominant_colors.append(color_info)
            
            return {
                "dominant_colors": dominant_colors,
                "primary_color": dominant_colors[0] if dominant_colors else None,
                "color_palette": [color["hex"] for color in dominant_colors]
            }
            
        except Exception as e:
            print(f"Error extracting dominant colors: {e}")
            return {
                "dominant_colors": [],
                "primary_color": None,
                "color_palette": []
            }
    
    def get_image_metadata(self, file_path):
        """Extract comprehensive metadata from image file"""
        try:
            file_path = Path(file_path)
            file_stats = file_path.stat()
            
            metadata = {
                "file_path": str(file_path.absolute()),
                "name": file_path.name,
                "file_size": file_stats.st_size,
                "file_size_mb": round(file_stats.st_size / (1024 * 1024), 2),
                "created_date": datetime.fromtimestamp(file_stats.st_ctime).isoformat(),
                "modified_date": datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
                "file_extension": file_path.suffix.lower(),
                "file_hash": self.get_file_hash(file_path)
            }
            
            # Image-specific metadata
            with Image.open(file_path) as img:
                metadata.update({
                    "width": img.width,
                    "height": img.height,
                    "aspect_ratio": round(img.width / img.height, 2),
                    "resolution": f"{img.width}x{img.height}",
                    "format": img.format,
                    "mode": img.mode,
                    "has_transparency": img.mode in ('RGBA', 'LA') or 'transparency' in img.info
                })
                
                color_data = self.extract_dominant_colors(img)
                metadata.update(color_data)
                
                exif_data = self.extract_exif_data(img)
                if exif_data:
                    metadata["exif"] = exif_data
                
                if img.info:
                    metadata["image_info"] = {k: str(v) for k, v in img.info.items()}
            
            metadata["description"] = self.generate_description(metadata)
            metadata["last_scanned"] = datetime.now().isoformat()
            
            return metadata
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            return None
    
    def generate_description(self, metadata):
        """Generate a description based on image metadata"""
        resolution = metadata.get("resolution", "Unknown")
        format_type = metadata.get("format", "Unknown")
        size_mb = metadata.get("file_size_mb", 0)
        
        description_parts = [
            f"{resolution} {format_type} wallpaper",
            f"({size_mb} MB)"
        ]
        
        aspect_ratio = metadata.get("aspect_ratio", 0)
        if aspect_ratio:
            if 1.7 <= aspect_ratio <= 1.8:
                description_parts.insert(-1, "widescreen")
            elif aspect_ratio > 2:
                description_parts.insert(-1, "ultrawide")
            elif 0.9 <= aspect_ratio <= 1.1:
                description_parts.insert(-1, "square")
            elif aspect_ratio < 0.9:
                description_parts.insert(-1, "portrait")
        
        primary_color = metadata.get("primary_color")
        if primary_color:
            color_name = primary_color.get("name", "").replace("_", " ")
            description_parts.insert(-1, f"primarily {color_name}")
        
        return " ".join(description_parts)
    
    def is_duplicate(self, file_hash, file_path):
        """Check if file is a duplicate based on hash"""
        if not file_hash:
            return False
            
        for existing_hash, existing_data in self.metadata_db.items():
            if existing_data.get("file_hash") == file_hash and existing_data.get("file_path") != str(file_path):
                return existing_data["file_path"]
        return False
    
    def scan_wallpapers(self):
        """Scan wallpaper folder and extract metadata"""
        if not self.wallpaper_folder.exists():
            print(f"Error: Wallpaper folder '{self.wallpaper_folder}' does not exist!")
            return
        
        # Supported image extensions
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp', '.ico'}
        
        print(f"Scanning wallpapers in: {self.wallpaper_folder}")
        print("-" * 50)
        
        processed_count = 0
        duplicate_count = 0
        error_count = 0
        
        for file_path in self.wallpaper_folder.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                print(f"Processing: {file_path.name}")
                
                metadata = self.get_image_metadata(file_path)
                if metadata:
                    # Check for duplicates
                    duplicate_path = self.is_duplicate(metadata["file_hash"], file_path)
                    if duplicate_path:
                        print(f"  → Duplicate found! Original: {duplicate_path}")
                        metadata["is_duplicate"] = True
                        metadata["original_file"] = duplicate_path
                        duplicate_count += 1
                    else:
                        metadata["is_duplicate"] = False
                    
                    self.metadata_db[str(file_path.absolute())] = metadata
                    processed_count += 1
                else:
                    error_count += 1
        
        print("-" * 50)
        print(f"Scan complete!")
        print(f"Processed: {processed_count} images")
        print(f"Duplicates found: {duplicate_count}")
        print(f"Errors: {error_count}")
        
        self.save_metadata()
    
    def save_metadata(self):
        """Save metadata database to JSON file"""
        try:
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata_db, f, indent=2, ensure_ascii=False)
            print(f"Metadata saved to: {self.json_file}")
        except Exception as e:
            print(f"Error saving metadata: {e}")
    
    def print_summary(self):
        """Print a summary of the metadata database"""
        if not self.metadata_db:
            print("No metadata available.")
            return
        
        total_files = len(self.metadata_db)
        total_size_mb = sum(data.get("file_size_mb", 0) for data in self.metadata_db.values())
        duplicates = sum(1 for data in self.metadata_db.values() if data.get("is_duplicate", False))
        
        resolutions = {}
        formats = {}
        
        color_names = {}
        
        for data in self.metadata_db.values():
            resolution = data.get("resolution", "Unknown")
            format_type = data.get("format", "Unknown")
            primary_color = data.get("primary_color")
            
            resolutions[resolution] = resolutions.get(resolution, 0) + 1
            formats[format_type] = formats.get(format_type, 0) + 1
            
            if primary_color:
                color_name = primary_color.get("name", "unknown").replace("_", " ")
                color_names[color_name] = color_names.get(color_name, 0) + 1
        
        print("\n" + "="*50)
        print("WALLPAPER COLLECTION SUMMARY")
        print("="*50)
        print(f"Total wallpapers: {total_files}")
        print(f"Total size: {total_size_mb:.2f} MB")
        print(f"Duplicates: {duplicates}")
        
        print(f"\nTop resolutions:")
        for resolution, count in sorted(resolutions.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {resolution}: {count} images")
        
        print(f"\nFormats:")
        for format_type, count in sorted(formats.items(), key=lambda x: x[1], reverse=True):
            print(f"  {format_type}: {count} images")
        
        print(f"\nDominant colors:")
        for color_name, count in sorted(color_names.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {color_name.title()}: {count} images")

def main():
    parser = argparse.ArgumentParser(description="Extract metadata from wallpaper images")
    parser.add_argument("folder", help="Path to wallpaper folder")
    parser.add_argument("-o", "--output", default="metadata.json", 
                       help="Output JSON file (default: metadata.json)")
    parser.add_argument("-s", "--summary", action="store_true", 
                       help="Show summary after scanning")
    
    args = parser.parse_args()
    
    extractor = WallpaperMetadataExtractor(args.folder, args.output)
    
    extractor.scan_wallpapers()
    
    if args.summary:
        extractor.print_summary()

if __name__ == "__main__":
    main()
