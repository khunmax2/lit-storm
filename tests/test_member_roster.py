import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend/demo_light'))
from member_roster import filter_members, page_members

class MemberRosterTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {'id':'1','display_name':'ADMIN','email':'admin@example.com','role':'admin','is_active':True},
            {'id':'2','display_name':'สมชาย','email':'somchai@example.com','role':'member','is_active':False},
            {'id':'3','display_name':'Mai','email':'mai@example.com','role':'member','is_active':True},
        ]
    def test_search_name_email_case_and_whitespace(self):
        self.assertEqual([r['id'] for r in filter_members(self.rows,'  ADMIN ')], ['1'])
        self.assertEqual([r['id'] for r in filter_members(self.rows,'สมชาย')], ['2'])
        self.assertEqual([r['id'] for r in filter_members(self.rows,'MAI@')], ['3'])
    def test_combined_filters_and_empty_result(self):
        self.assertEqual([r['id'] for r in filter_members(self.rows,'example','member','suspended')], ['2'])
        self.assertEqual(filter_members(self.rows,'nobody'), [])
    def test_page_bounds_and_empty_result(self):
        self.assertEqual(page_members(self.rows, 99, 2)[1:], (2,2))
        self.assertEqual([r['id'] for r in page_members(self.rows,2,2)[0]], ['3'])
        self.assertEqual(page_members([],99), ([],1,1))

if __name__ == '__main__': unittest.main()
