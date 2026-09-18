#!/usr/bin/env python3
"""
Script to convert an image to favicon format.
Usage: python3 create_favicon.py <input_image_path>
"""

from PIL import Image
import sys
import os

def create_favicon(input_path, output_path='static/favicon.ico'):
    """Convert an image to favicon format with multiple sizes."""
    
    # Open the input image
    try:
        img = Image.open(input_path)
    except Exception as e:
        print(f"Error opening image: {e}")
        return False
    
    # Convert to RGBA if not already
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    # Create multiple sizes for the favicon
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64)]
    
    # Resize image to each size
    favicon_images = []
    for size in sizes:
        resized = img.resize(size, Image.Resampling.LANCZOS)
        favicon_images.append(resized)
    
    # Save as ICO with multiple sizes
    try:
        # Save each size separately
        for i, size in enumerate(sizes):
            individual_output = output_path.replace('.ico', f'_{size[0]}x{size[1]}.png')
            favicon_images[i].save(individual_output, format='PNG')
            print(f"Created {individual_output}")
        
        # Create a basic ICO with the 32x32 size (most common)
        favicon_images[1].save(output_path, format='ICO')
        print(f"Favicon created successfully: {output_path}")
        print(f"Main favicon size: 32x32")
        print(f"Additional PNG sizes created: {sizes}")
        return True
    except Exception as e:
        print(f"Error saving favicon: {e}")
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 create_favicon.py <input_image_path>")
        sys.exit(1)
    
    input_path = sys.argv[1]
    if not os.path.exists(input_path):
        print(f"Error: File not found: {input_path}")
        sys.exit(1)
    
    create_favicon(input_path)