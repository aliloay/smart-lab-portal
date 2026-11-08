"""Enrolment quality gate (pure function; no camera, no faces of real people)."""
import cv2
import numpy as np

import face_server as fs


def _sharp(h=120):
    rng = np.random.default_rng(0)
    return rng.integers(0, 255, (h, h), dtype=np.uint8)


def test_good_sample_passes():
    assert fs.enroll_quality(_sharp(), 1) is None


def test_two_faces_rejected():
    assert "more than one face" in fs.enroll_quality(_sharp(), 2)


def test_small_face_rejected():
    assert "too small" in fs.enroll_quality(_sharp(40), 1)


def test_blurred_rejected():
    blurred = cv2.GaussianBlur(_sharp(), (31, 31), 10)
    assert "blurred" in fs.enroll_quality(blurred, 1)


def test_repeat_rejected():
    v = np.ones(128) / np.sqrt(128)
    assert "same as the last" in fs.enroll_quality(_sharp(), 1, v, v)
    w = v.copy(); w[:64] *= -1
    assert fs.enroll_quality(_sharp(), 1, w, v) is None
