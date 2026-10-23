"""Photo ratios are based on visible placement area, not file counts."""
import unittest
try:
    from proposition_runtime.layout import assess_placements
except ImportError:
    assess_placements = None


class LayoutTests(unittest.TestCase):
    def test_one_large_synthetic_image_cannot_hide_behind_many_tiny_photos(self):
        self.assertIsNotNone(assess_placements)
        rows = [{'page':'1','kind':'synthetic','rect':[0,0,90,100],'source_id':'a'}]
        rows += [{'page':'1','kind':'authentic','rect':[90,i*10,10,10],'source_id':str(i)} for i in range(10)]
        report = assess_placements(rows, {'1':[100,100]})
        self.assertEqual(report['synthetic_photo_fraction'], .9)
        self.assertEqual(report['status'], 'FAIL')

    def test_unclassified_and_overlapping_media_require_review(self):
        self.assertIsNotNone(assess_placements)
        rows = [{'page':'1','kind':'authentic','rect':[0,0,100,100],'source_id':'a'},
                {'page':'1','kind':'synthetic','rect':[50,0,50,100],'source_id':'b'}]
        report = assess_placements(rows, {'1':[100,100]})
        self.assertEqual(report['status'], 'BLOCKED')
        self.assertIsNone(report['synthetic_photo_fraction'])
        rows = [{'page':'1','kind':'unclassified','rect':[0,0,100,100]}]
        self.assertEqual(assess_placements(rows, {'1':[100,100]})['status'], 'BLOCKED')

    def test_repeated_placements_count_each_visible_occurrence(self):
        self.assertIsNotNone(assess_placements)
        rows = [{'page':str(i),'kind':'authentic','rect':[0,0,80,100],'source_id':'same'} for i in range(2)]
        rows += [{'page':str(i),'kind':'synthetic','rect':[80,0,20,100],'source_id':'b'} for i in range(2)]
        report = assess_placements(rows, {'0':[100,100], '1':[100,100]})
        self.assertEqual(report['synthetic_photo_fraction'], .2)
        self.assertEqual(report['photo_area'], 20000)
        self.assertEqual(report['status'], 'PASS')


if __name__ == '__main__': unittest.main()
