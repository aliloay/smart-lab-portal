"""Zoomed re-detection where a named person was lost (lab 2026-10-14: Ali behind Nour)."""
import numpy as np

from vision import PERSON, Detection, zoom_people


class FakeDet:
    """Returns, in crop coordinates, whatever people lie inside the crop."""
    def __init__(self, people): self.people, self.crops = people, []
    def detect(self, crop):
        self.crops.append(crop.shape)
        return [Detection(PERSON, 0.8, b) for b in self.people]


def test_found_person_is_returned_in_frame_coordinates():
    frame = np.zeros((540, 960, 3), np.uint8)
    det = FakeDet([(10, 5, 50, 70)])                        # inside the crop
    lost = [(640, 330, 60, 80)]                             # where Ali was lost
    got = zoom_people(det, frame, lost, existing=[(637, 341, 108, 138)])
    x0, y0 = int(640 - 0.6 * 60), int(330 - 0.6 * 80)
    assert got == [(10 + x0, 5 + y0, 50, 70)]


def test_a_person_already_boxed_is_not_added_twice():
    frame = np.zeros((540, 960, 3), np.uint8)
    existing = [(637, 341, 108, 138)]
    x0, y0 = int(640 - 0.6 * 60), int(330 - 0.6 * 80)
    det = FakeDet([(637 - x0, 341 - y0, 108, 138)])         # the same person the full frame found
    assert zoom_people(det, frame, [(640, 330, 60, 80)], existing) == []


def test_at_most_two_zooms_per_pass():
    frame = np.zeros((540, 960, 3), np.uint8)
    det = FakeDet([])
    zoom_people(det, frame, [(100, 100, 50, 80)] * 5, [])
    assert len(det.crops) == 2


def test_a_sliver_inside_an_existing_box_is_not_a_new_person():
    frame = np.zeros((540, 960, 3), np.uint8)
    existing = [(764, 340, 81, 194)]                          # the lab frame's person on the right
    x0, y0 = int(700 - 0.6 * 60), int(330 - 0.6 * 80)
    det = FakeDet([(787 - x0, 348 - y0, 25, 181)])            # the 25 px strip the zoom returned
    assert zoom_people(det, frame, [(700, 330, 60, 80)], existing) == []
