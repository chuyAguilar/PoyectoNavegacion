import cv2
from math3d.transforms import Transform
from project.tracking.instrument_board import create_instrument_board


class ArucoTracker:
    def __init__(self, marker_length, camera_matrix, dist_coeffs):
        self.marker_length = marker_length
        self.camera_matrix = camera_matrix
        self.dist_coeffs = dist_coeffs
        self.board, self.tip_offset = create_instrument_board()

        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
        self.parameters = cv2.aruco.DetectorParameters()

        self.parameters.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        self.parameters.adaptiveThreshWinSizeMin = 3
        self.parameters.adaptiveThreshWinSizeMax = 23
        self.parameters.adaptiveThreshWinSizeStep = 10
        self.parameters.minMarkerPerimeterRate = 0.02
        self.parameters.maxMarkerPerimeterRate = 4.0
        self.parameters.cornerRefinementMaxIterations = 50
        self.parameters.cornerRefinementMinAccuracy = 0.01
        self.parameters.cornerRefinementWinSize = 5
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.parameters)

    def detect(self, frame):

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        corners, ids, rejected = self.detector.detectMarkers(gray)

        transforms = {}
        rvecs = None

        if ids is not None:
            # 1. Detectar poses individuales para los marcadores de referencia (0 y 1)
            rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
                corners, self.marker_length, self.camera_matrix, self.dist_coeffs
            )

            for i in range(len(ids)):
                marker_id = int(ids[i][0])
                if marker_id in [0, 1]:
                    T = Transform.from_rvec_tvec(rvecs[i], tvecs[i])
                    transforms[marker_id] = T

            # 2. Estimar pose del instrumento usando el board
            retval, rvec, tvec = cv2.aruco.estimatePoseBoard(
                corners,
                ids,
                self.board,
                self.camera_matrix,
                self.dist_coeffs,
                None,
                None
            )

            if retval > 0:
                T = Transform.from_rvec_tvec(rvec, tvec)
                transforms["instrument"] = T

        return transforms, corners, ids, rvecs
