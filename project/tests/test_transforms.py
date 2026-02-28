import numpy as np
from math3d.transforms import Transform


def test_identity_inverse():
    T = Transform.identity()
    T_inv = T.inverse()
    result = T @ T_inv

    assert np.allclose(result.matrix(), np.eye(4), atol=1e-9)


def test_inverse_of_inverse():
    R = np.eye(3)
    t = np.array([1.0, 2.0, 3.0])
    T = Transform.from_rotation_translation(R, t)

    T_back = T.inverse().inverse()
    assert np.allclose(T.matrix(), T_back.matrix(), atol=1e-9)


def test_composition_rule():
    # Define frames:
    # b está 1m en X respecto a a
    T_a_b = Transform.from_rotation_translation(
        np.eye(3),
        np.array([1.0, 0.0, 0.0])
    )

    # c está 2m en Y respecto a b
    T_b_c = Transform.from_rotation_translation(
        np.eye(3),
        np.array([0.0, 2.0, 0.0])
    )

    # Entonces c respecto a a debería estar en (1,2,0)
    T_a_c = T_a_b @ T_b_c

    expected_translation = np.array([1.0, 2.0, 0.0])
    assert np.allclose(T_a_c.translation(), expected_translation, atol=1e-9)


def test_inverse_property():
    R = np.eye(3)
    t = np.array([0.3, -0.4, 1.2])
    T = Transform.from_rotation_translation(R, t)

    I = T @ T.inverse()
    assert np.allclose(I.matrix(), np.eye(4), atol=1e-9)

def test_rotation_90deg_z():
    theta = np.pi / 2

    Rz = np.array([
        [np.cos(theta), -np.sin(theta), 0],
        [np.sin(theta),  np.cos(theta), 0],
        [0,              0,             1]
    ])

    T = Transform.from_rotation_translation(Rz, np.zeros(3))

    R_result = T.rotation()

    assert np.allclose(R_result, Rz, atol=1e-9)

def test_rotation_then_translation():
    theta = np.pi / 2

    Rz = np.array([
        [np.cos(theta), -np.sin(theta), 0],
        [np.sin(theta),  np.cos(theta), 0],
        [0,              0,             1]
    ])

    T_a_b = Transform.from_rotation_translation(Rz, np.zeros(3))

    T_b_c = Transform.from_rotation_translation(
        np.eye(3),
        np.array([1.0, 0.0, 0.0])
    )

    T_a_c = T_a_b @ T_b_c

    expected = np.array([0.0, 1.0, 0.0])

    assert np.allclose(T_a_c.translation(), expected, atol=1e-9)

def test_rotation_orthogonality():
    theta = np.pi / 3

    Rz = np.array([
        [np.cos(theta), -np.sin(theta), 0],
        [np.sin(theta),  np.cos(theta), 0],
        [0,              0,             1]
    ])

    T = Transform.from_rotation_translation(Rz, np.zeros(3))

    R = T.rotation()

    identity = R.T @ R

    assert np.allclose(identity, np.eye(3), atol=1e-9)

def test_rotation_determinant():
    theta = np.pi / 4

    Rz = np.array([
        [np.cos(theta), -np.sin(theta), 0],
        [np.sin(theta),  np.cos(theta), 0],
        [0,              0,             1]
    ])

    T = Transform.from_rotation_translation(Rz, np.zeros(3))

    R = T.rotation()

    det = np.linalg.det(R)

    assert np.isclose(det, 1.0, atol=1e-9)