"""
Berita Acara and BQ database models
"""
from datetime import datetime

def create_models(db):
    """Create and return the model classes"""
    
    class BeritaAcara(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        nomor = db.Column(db.String(50), nullable=False)
        tanggal = db.Column(db.Date, nullable=False)
        waktu = db.Column(db.String(10), nullable=False)
        lokasi = db.Column(db.Text, nullable=False)
        deskripsi = db.Column(db.Text, nullable=False)
        analisa = db.Column(db.Text, nullable=False)
        solusi = db.Column(db.Text, nullable=False)
        staff_engineering = db.Column(db.String(100), nullable=False)
        supervisor = db.Column(db.String(100), nullable=False)
        asst_manager = db.Column(db.String(100), nullable=False)
        property_manager = db.Column(db.String(100), nullable=False)
        gambar_paths = db.Column(db.Text)  # Store as comma-separated paths
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        
        __tablename__ = 'berita_acara'

    class BQItem(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        bq_id = db.Column(db.Integer, db.ForeignKey('bq.id'), nullable=False)
        item_no = db.Column(db.String(10), nullable=False)
        item_description = db.Column(db.Text, nullable=False)
        qty = db.Column(db.Float, nullable=False)
        unit = db.Column(db.String(20), nullable=False)
        material_price = db.Column(db.Float, default=0)
        labor_price = db.Column(db.Float, default=0)
        
        __tablename__ = 'bq_items'

    class BQ(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        nomor = db.Column(db.String(50), nullable=False)
        project = db.Column(db.String(200), nullable=False)
        kontraktor = db.Column(db.String(200), nullable=False)
        location = db.Column(db.Text, nullable=False)
        dibuat_oleh = db.Column(db.String(100), nullable=False)
        menyetujui = db.Column(db.String(100), nullable=False)
        mengetahui = db.Column(db.String(100), nullable=False)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        items = db.relationship('BQItem', backref='bq', lazy=True, cascade='all, delete-orphan')
        
        __tablename__ = 'bq'

        @property
        def subtotal(self):
            return sum((item.qty * (item.material_price or 0) + item.qty * (item.labor_price or 0)) for item in self.items)

        @property
        def ppn(self):
            return self.subtotal * 0.11

        @property
        def grand_total(self):
            return self.subtotal + self.ppn
    
    return BeritaAcara, BQ, BQItem