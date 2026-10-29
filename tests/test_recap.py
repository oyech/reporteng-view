import unittest
from datetime import date
from unittest.mock import Mock, patch
from app import app, format_daily_recap


def make_report(area, unit, job, status):
    return {
        'id': '1',
        'tanggal': '2026-10-22T08:00:00+07:00',
        'area_kerja': area,
        'unit_area': unit,
        'pekerjaan': job,
        'status': status,
        'pic': 'Budi',
        'foto': []
    }


class DailyRecapTests(unittest.TestCase):
    def test_format_daily_recap_matches_sample_format(self):
        rows = [
            make_report('Tower A', 'CTA-36B', 'pengecekan indikasi membocori unit bawah area kamar mandi anak Hasilnya: - kloset bocor,jadwalkan perbaikan', 'berlanjut'),
            make_report('Tower A', 'CTA-17G', 'pemasangan grease trap Hasilnya: - pemasangan grease trap', 'Selesai'),
            make_report('Tower B', 'CTB-03I', 'perbaikan bongkar pasang kloset kloset, nat lantai', 'done'),
            make_report('Tower C', 'STC-05J', 'perbaikan Nat kamar mandi', 'Selesai'),
            make_report('Tower C', 'STC-05J', 'STC-05J Perbaikan floor drain shower Tower C', 'done'),
        ]

        output = format_daily_recap(rows, title='*Tim RM Reguler PIC Tower*')
        
        # Verify title
        self.assertTrue(output.startswith('*Tim RM Reguler PIC Tower*'))
        
        # Verify area headings
        self.assertIn('*Tower A*', output)
        self.assertIn('*Tower B*', output)
        self.assertIn('*Tower C*', output)
        
        # Verify bullets match View menu writing format: [Unit] [Capitalized Description] ([Status])
        self.assertIn('• CTA-36B Pengecekan indikasi membocori unit bawah area kamar mandi anak Hasilnya: - kloset bocor,jadwalkan perbaikan (berlanjut)', output)
        self.assertIn('• CTA-17G Pemasangan grease trap Hasilnya: - pemasangan grease trap (Selesai)', output)
        self.assertIn('• CTB-03I Perbaikan bongkar pasang kloset kloset, nat lantai (done)', output)
        self.assertIn('• STC-05J Perbaikan Nat kamar mandi (Selesai)', output)
        
        # Verify unit is not duplicated if already at start of pekerjaan
        self.assertIn('• STC-05J Perbaikan floor drain shower Tower C (done)', output)
        self.assertNotIn('STC-05J STC-05J', output)

    def test_format_daily_recap_empty_rows(self):
        output = format_daily_recap([], title='*Tim RM Reguler PIC Tower*')
        self.assertIn('*Tim RM Reguler PIC Tower*', output)
        self.assertIn('Tidak ada pekerjaan', output)

    def test_format_daily_recap_custom_title_and_fallback_area(self):
        rows = [
            make_report('Civil', 'lantai 1', 'pengecatan koridor', 'Selesai'),
            make_report('Civil', 'area kolam', 'pembersihan filter', 'Proses'),
            make_report('Taman', '', 'pemotongan rumput', 'Proses'),
        ]
        output = format_daily_recap(rows, title='Laporan Harian Civil')
        self.assertTrue(output.startswith('*Laporan Harian Civil*'))
        self.assertIn('*Civil*', output)
        self.assertIn('• LANTAI-1 Pengecatan koridor (Selesai)', output)
        self.assertIn('• Area Kolam Pembersihan filter (Proses)', output)
        self.assertIn('*Taman*', output)
        self.assertIn('• Taman Pemotongan rumput (Proses)', output)

    def test_format_unit_area_regex_and_capitalization(self):
        rows = [
            make_report('Tower A', 'cta 12a', 'perbaikan kran', 'ProgressStatus.Selesai'),
        ]
        output = format_daily_recap(rows)
        self.assertIn('• CTA-12A Perbaikan kran (Selesai)', output)

    def test_area_ordering_tower_first_then_public_area_then_others(self):
        rows = [
            make_report('Club House', 'Kolam', 'Pembersihan kolam', 'Selesai'),
            make_report('Public Area', 'Lobby', 'Perbaikan pintu', 'Selesai'),
            make_report('Tower B', 'CTB-02', 'Cek hydrant', 'Selesai'),
            make_report('Civil', 'Gudang', 'Pengecatan pintu', 'Selesai'),
            make_report('Tower A', 'CTA-01', 'Cek valve', 'Selesai'),
            make_report('Public Area MEP', 'Basement', 'Perbaikan lampu', 'Proses'),
        ]
        output = format_daily_recap(rows)

        # Find the index of each section heading in output
        idx_tower_a = output.index('*Tower A*')
        idx_tower_b = output.index('*Tower B*')
        idx_public_area = output.index('*Public Area*')
        idx_public_mep = output.index('*Public Area MEP*')
        idx_civil = output.index('*Civil*')
        idx_club_house = output.index('*Club House*')

        # Towers first
        self.assertLess(idx_tower_a, idx_tower_b)
        self.assertLess(idx_tower_b, idx_public_area)

        # Then Public Area
        self.assertLess(idx_public_area, idx_public_mep)
        self.assertLess(idx_public_mep, idx_civil)

        # Then others
        self.assertLess(idx_civil, idx_club_house)

    def test_shift_reports_excluded_from_recap(self):
        rows = [
            make_report('Tower A', 'CTA-05', 'Perbaikan pipa', 'Selesai'),
            make_report('Shift Pagi', 'Genset', 'Standby genset', 'Selesai'),
            make_report('Shift Siang', 'Panel', 'Pemeriksaan beban', 'Proses'),
            make_report('Shift Malam', 'Chiller', 'Patroli malam', 'Selesai'),
            make_report('Public Area', 'Taman', 'Penyiraman tanaman', 'Selesai'),
        ]
        output = format_daily_recap(rows)

        self.assertIn('*Tower A*', output)
        self.assertIn('*Public Area*', output)
        self.assertNotIn('*Shift Pagi*', output)
        self.assertNotIn('*Shift Siang*', output)
        self.assertNotIn('*Shift Malam*', output)
        self.assertNotIn('Patroli malam', output)

    def test_api_recap_endpoint(self):
        with patch('auth.get_identity', return_value={'token': 'test-token', 'email': 'test@example.com'}), \
             patch('app.fetch_reports') as mock_fetch:
            mock_fetch.return_value = [
                make_report('Tower B', 'CTB-12B', 'Ganti lampu', 'proses'),
                make_report('Shift Malam', 'Ruang Pompa', 'Patroli shift', 'done'),
                make_report('Public Area', 'Lobby Utama', 'Cek kaca', 'done'),
                make_report('Tower A', 'CTA-10A', 'Cek genset', 'done'),
            ]
            client = app.test_client()
            res = client.get('/api/reports/recap?date=2026-10-22')
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data.get('ok'))
            # Shift Malam is excluded, so count is 3
            self.assertEqual(data.get('count'), 3)
            # Areas ordered: Tower A, Tower B, Public Area (no Shift Malam)
            self.assertEqual(data.get('areas'), ['Tower A', 'Tower B', 'Public Area'])
            self.assertIn('*Tower A*', data.get('text'))
            self.assertIn('*Tower B*', data.get('text'))
            self.assertIn('*Public Area*', data.get('text'))
            self.assertNotIn('Shift Malam', data.get('text'))


if __name__ == '__main__':
    unittest.main()
