#!/usr/bin/env python3
"""
Script to migrate data from old berita_acara_app database to new integrated database
"""
import sqlite3
import os
from datetime import datetime

# Paths
old_db_path = "/Volumes/DATA SHARING ENG/web_app/berita_acara_app/instance/berita_acara.db"
new_db_path = "instance/berita_acara.db"

# File paths for uploads
old_uploads_dir = "/Volumes/DATA SHARING ENG/web_app/berita_acara_app/uploads"
new_uploads_dir = "uploads"

def migrate_berita_acara():
    """Migrate berita_acara table"""
    old_conn = sqlite3.connect(old_db_path)
    new_conn = sqlite3.connect(new_db_path)
    
    old_cursor = old_conn.cursor()
    new_cursor = new_conn.cursor()
    
    # Get all data from old database
    old_cursor.execute("SELECT * FROM berita_acara")
    rows = old_cursor.fetchall()
    
    print(f"Found {len(rows)} berita acara records to migrate")
    
    # Get column names
    old_cursor.execute("PRAGMA table_info(berita_acara)")
    columns = [column[1] for column in old_cursor.fetchall()]
    print(f"Columns: {columns}")
    
    # Migrate each record
    for row in rows:
        try:
            # Convert row to dict
            row_dict = dict(zip(columns, row))
            
            # Prepare values for insertion
            values = (
                row_dict['nomor'],
                row_dict['tanggal'],
                row_dict['waktu'],
                row_dict['lokasi'],
                row_dict['deskripsi'],
                row_dict['analisa'],
                row_dict['solusi'],
                row_dict['staff_engineering'],
                row_dict['supervisor'],
                row_dict['asst_manager'],
                row_dict['property_manager'],
                row_dict['gambar_paths'],
                row_dict['created_at']
            )
            
            # Insert into new database
            new_cursor.execute("""
                INSERT INTO berita_acara 
                (nomor, tanggal, waktu, lokasi, deskripsi, analisa, solusi, 
                 staff_engineering, supervisor, asst_manager, property_manager, 
                 gambar_paths, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, values)
            
            print(f"Migrated: {row_dict['nomor']}")
            
        except Exception as e:
            print(f"Error migrating row {row_dict.get('nomor', 'unknown')}: {e}")
    
    new_conn.commit()
    new_conn.close()
    old_conn.close()
    print("Berita acara migration completed")

def migrate_bq():
    """Migrate bq and bq_item tables"""
    old_conn = sqlite3.connect(old_db_path)
    new_conn = sqlite3.connect(new_db_path)
    
    old_cursor = old_conn.cursor()
    new_cursor = new_conn.cursor()
    
    # Get all BQ records
    old_cursor.execute("SELECT * FROM bq")
    bq_rows = old_cursor.fetchall()
    
    # Get column names for BQ
    old_cursor.execute("PRAGMA table_info(bq)")
    bq_columns = [column[1] for column in old_cursor.fetchall()]
    
    print(f"Found {len(bq_rows)} BQ records to migrate")
    
    # Create mapping for old BQ IDs to new BQ IDs
    bq_id_mapping = {}
    
    # Migrate BQ records
    for row in bq_rows:
        try:
            row_dict = dict(zip(bq_columns, row))
            
            values = (
                row_dict['nomor'],
                row_dict['project'],
                row_dict['kontraktor'],
                row_dict['location'],
                row_dict['dibuat_oleh'],
                row_dict['menyetujui'],
                row_dict['mengetahui'],
                row_dict['created_at']
            )
            
            new_cursor.execute("""
                INSERT INTO bq 
                (nomor, project, kontraktor, location, dibuat_oleh, menyetujui, mengetahui, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, values)
            
            new_bq_id = new_cursor.lastrowid
            old_bq_id = row_dict['id']
            bq_id_mapping[old_bq_id] = new_bq_id
            
            print(f"Migrated BQ: {row_dict['nomor']} (old ID: {old_bq_id} -> new ID: {new_bq_id})")
            
        except Exception as e:
            print(f"Error migrating BQ {row_dict.get('nomor', 'unknown')}: {e}")
    
    # Migrate BQ items (note: old table is bq_item, new table is bq_items)
    old_cursor.execute("SELECT * FROM bq_item")
    item_rows = old_cursor.fetchall()
    
    old_cursor.execute("PRAGMA table_info(bq_item)")
    item_columns = [column[1] for column in old_cursor.fetchall()]
    
    print(f"Found {len(item_rows)} BQ item records to migrate")
    
    for row in item_rows:
        try:
            row_dict = dict(zip(item_columns, row))
            old_bq_id = row_dict['bq_id']
            new_bq_id = bq_id_mapping.get(old_bq_id)
            
            if new_bq_id:
                values = (
                    new_bq_id,
                    row_dict['item_no'],
                    row_dict['item_description'],
                    row_dict['qty'],
                    row_dict['unit'],
                    row_dict['material_price'],
                    row_dict['labor_price']
                )
                
                new_cursor.execute("""
                    INSERT INTO bq_items 
                    (bq_id, item_no, item_description, qty, unit, material_price, labor_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, values)
                
                print(f"Migrated BQ item: {row_dict['item_no']} for BQ ID {new_bq_id}")
            else:
                print(f"Warning: Could not find new BQ ID for old BQ ID {old_bq_id}")
                
        except Exception as e:
            print(f"Error migrating BQ item: {e}")
    
    new_conn.commit()
    new_conn.close()
    old_conn.close()
    print("BQ migration completed")

def migrate_images():
    """Copy images from old uploads to new uploads"""
    old_images_dir = old_uploads_dir
    new_images_dir = new_uploads_dir
    
    if not os.path.exists(old_images_dir):
        print(f"Old uploads directory not found: {old_images_dir}")
        return
    
    if not os.path.exists(new_images_dir):
        os.makedirs(new_images_dir)
        print(f"Created new uploads directory: {new_images_dir}")
    
    # Copy all images
    import shutil
    copied_count = 0
    
    for filename in os.listdir(old_images_dir):
        if filename.endswith(('.jpg', '.jpeg', '.png', '.gif')):
            old_path = os.path.join(old_images_dir, filename)
            new_path = os.path.join(new_images_dir, filename)
            
            try:
                shutil.copy2(old_path, new_path)
                copied_count += 1
                print(f"Copied: {filename}")
            except Exception as e:
                print(f"Error copying {filename}: {e}")
    
    print(f"Image migration completed. Copied {copied_count} images.")

if __name__ == '__main__':
    print("Starting data migration...")
    
    # Check if old database exists
    if not os.path.exists(old_db_path):
        print(f"Old database not found: {old_db_path}")
        print("Skipping migration.")
    else:
        # Migrate Berita Acara
        migrate_berita_acara()
        
        # Migrate BQ
        migrate_bq()
        
        # Migrate images
        migrate_images()
    
    print("Data migration completed!")