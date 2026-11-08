import sqlite3
import tempfile
import unittest
from pathlib import Path
from subject_wizard_core import ensure_schema, create_draft_enrollment, write_template_scaffold

class SubjectWizardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.conn = sqlite3.connect(self.root / 'test.db')
        self.conn.execute('CREATE TABLE boards (id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL, active INTEGER DEFAULT 1)')
        self.conn.execute("INSERT INTO boards VALUES (1,'HR','Haryana Board',1)")
        self.conn.execute('CREATE TABLE questions (id INTEGER PRIMARY KEY, class_level TEXT, subject TEXT)')
        self.conn.executemany('INSERT INTO questions(class_level,subject) VALUES (?,?)', [('LKG','MATH')]*66)
        self.conn.commit()
        self.before_lkg_count = self.conn.execute("SELECT count(*) FROM questions WHERE class_level='LKG' AND subject='MATH'").fetchone()[0]
        ensure_schema(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_create_target_as_inactive_draft(self):
        row = create_draft_enrollment(self.conn, board_code='HR', class_level='UKG', subject='ENGLISH')
        self.assertEqual(row['subject_code'], 'UKG-ENGLISH')
        self.assertEqual(row['status'], 'DRAFT')
        self.assertFalse(row['activated'])
        self.assertEqual(self.conn.execute('SELECT count(*) FROM questions').fetchone()[0], 66)

    def test_duplicate_enrollment_is_rejected(self):
        create_draft_enrollment(self.conn, board_code='HR', class_level='UKG', subject='ENGLISH')
        with self.assertRaises(sqlite3.IntegrityError):
            create_draft_enrollment(self.conn, board_code='HR', class_level='UKG', subject='ENGLISH')

    def test_invalid_class_rejected(self):
        with self.assertRaises(ValueError):
            create_draft_enrollment(self.conn, board_code='HR', class_level='../UKG', subject='ENGLISH')

    def test_template_scaffold_does_not_overwrite(self):
        row = create_draft_enrollment(self.conn, board_code='HR', class_level='UKG', subject='ENGLISH')
        path = write_template_scaffold(self.root / 'templates', row)
        self.assertTrue(path.is_file())
        with self.assertRaises(FileExistsError):
            write_template_scaffold(self.root / 'templates', row)

    def test_lkg_math_baseline_preserved(self):
        self.assertEqual(self.conn.execute("SELECT count(*) FROM questions WHERE class_level='LKG' AND subject='MATH'").fetchone()[0], self.before_lkg_count)

if __name__ == '__main__':
    unittest.main()
