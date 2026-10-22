import unittest

from scripts.preload_hanoi import profile_bbox, tiled_bboxes
from src.map_service import bbox_contains, bbox_dimensions_km


class PreloadTests(unittest.TestCase):
    def test_west_profile_is_split_into_small_overlapping_tiles(self):
        bbox = profile_bbox("west")
        tiles = tiled_bboxes(bbox)
        self.assertGreater(len(tiles), 1)
        self.assertTrue(all(bbox_contains(bbox, tile) for tile in tiles))
        self.assertLess(min(tile[0] for tile in tiles), 105.5)
        self.assertGreater(max(tile[2] for tile in tiles), 105.85)
        for tile in tiles:
            width, height = bbox_dimensions_km(tile)
            self.assertLess(width, 15)
            self.assertLess(height, 15)


if __name__ == "__main__":
    unittest.main()
