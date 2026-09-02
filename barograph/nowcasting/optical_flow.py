"""Optical flow estimation for radar nowcasting."""

from __future__ import annotations

import numpy as np


class OpticalFlowNowcaster:
    """Estimate storm motion and extrapolate radar reflectivity.

    Uses either dense optical flow (Farneback via OpenCV) or a simpler
    block-matching / Lucas-Kanade sparse approach. The resulting motion field
    is used to advect the most recent radar sweep forward in time.
    """

    def __init__(
        self,
        method: str = "farneback",
        pyr_scale: float = 0.5,
        levels: int = 3,
        winsize: int = 15,
        iterations: int = 3,
        poly_n: int = 5,
        poly_sigma: float = 1.2,
    ):
        if method not in ("farneback", "lucas_kanade", "block"):
            raise ValueError(f"Unknown optical flow method: {method}")
        self.method = method
        self.pyr_scale = pyr_scale
        self.levels = levels
        self.winsize = winsize
        self.iterations = iterations
        self.poly_n = poly_n
        self.poly_sigma = poly_sigma

    def _normalize(self, img: np.ndarray) -> np.ndarray:
        """Normalize reflectivity to [0, 1] float for flow estimation."""
        img = np.asarray(img, dtype=np.float64)
        min_v = np.nanmin(img)
        max_v = np.nanmax(img)
        if max_v <= min_v:
            return np.zeros_like(img)
        return (img - min_v) / (max_v - min_v)

    def compute_flow(
        self,
        frame1: np.ndarray,
        frame2: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Compute optical flow from frame1 to frame2.

        Returns (u, v) displacement field in pixels.
        """
        f1 = self._normalize(frame1)
        f2 = self._normalize(frame2)

        if self.method == "farneback":
            return self._farneback(f1, f2)
        elif self.method == "lucas_kanade":
            return self._lucas_kanade(f1, f2)
        else:
            return self._block_matching(f1, f2)

    def _farneback(
        self, f1: np.ndarray, f2: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        try:
            import cv2
        except ImportError as e:
            raise ImportError(
                "opencv-python is required for the farneback method"
            ) from e

        p1 = (f1 * 255).astype(np.uint8)
        p2 = (f2 * 255).astype(np.uint8)

        flow = cv2.calcOpticalFlowFarneback(  # type: ignore[call-overload]
            p1, p2,
            flow=None,
            pyr_scale=self.pyr_scale,
            levels=self.levels,
            winsize=self.winsize,
            iterations=self.iterations,
            poly_n=self.poly_n,
            poly_sigma=self.poly_sigma,
            flags=0,
        )
        u = flow[..., 0]
        v = flow[..., 1]
        return u, v

    def _lucas_kanade(
        self, f1: np.ndarray, f2: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        try:
            import cv2
        except ImportError as e:
            raise ImportError(
                "opencv-python is required for the lucas_kanade method"
            ) from e

        p1 = (f1 * 255).astype(np.uint8)
        p2 = (f2 * 255).astype(np.uint8)

        # Detect good features to track (grid of points)
        step = max(8, p1.shape[0] // 20)
        y_coords, x_coords = np.mgrid[step // 2:p1.shape[0]:step, step // 2:p1.shape[1]:step]
        pts = np.column_stack([x_coords.ravel(), y_coords.ravel()]).astype(np.float32)

        if len(pts) == 0:
            return np.zeros_like(f1), np.zeros_like(f1)

        next_pts, st, err = cv2.calcOpticalFlowPyrLK(  # type: ignore[call-overload]
            p1, p2, pts, None,
            winSize=(self.winsize, self.winsize),
            maxLevel=self.levels,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
        )

        u = np.full_like(f1, np.nan)
        v = np.full_like(f1, np.nan)

        valid = st.ravel() == 1
        if np.any(valid):
            pts_v = pts[valid]
            nxt_v = next_pts[valid]
            u[y_coords.ravel()[valid], x_coords.ravel()[valid]] = (
                nxt_v[:, 0] - pts_v[:, 0]
            )
            v[y_coords.ravel()[valid], x_coords.ravel()[valid]] = (
                nxt_v[:, 1] - pts_v[:, 1]
            )

        # Interpolate sparse flow to dense grid
        from scipy.interpolate import griddata
        good = ~np.isnan(u)
        if np.sum(good) < 3:
            return np.zeros_like(f1), np.zeros_like(f1)

        pts_flat = np.column_stack([
            np.where(good)[1], np.where(good)[0]
        ])
        grid_x, grid_y = np.meshgrid(np.arange(f1.shape[1]), np.arange(f1.shape[0]))
        u_dense = griddata(pts_flat, u[good], (grid_x, grid_y), method="cubic", fill_value=0)
        v_dense = griddata(pts_flat, v[good], (grid_x, grid_y), method="cubic", fill_value=0)

        return np.nan_to_num(u_dense), np.nan_to_num(v_dense)

    def _block_matching(
        self, f1: np.ndarray, f2: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """Simple block matching with a fixed search window."""
        ny, nx = f1.shape
        block = 16
        search = self.winsize

        u = np.zeros_like(f1)
        v = np.zeros_like(f1)

        for cy in range(block // 2, ny, block):
            for cx in range(block // 2, nx, block):
                y0, y1 = max(0, cy - block // 2), min(ny, cy + block // 2)
                x0, x1 = max(0, cx - block // 2), min(nx, cx + block // 2)
                template = f1[y0:y1, x0:x1]

                best_cost = np.inf
                best_dy, best_dx = 0, 0
                for dy in range(-search, search + 1):
                    for dx in range(-search, search + 1):
                        ty0 = y0 + dy
                        ty1 = y1 + dy
                        tx0 = x0 + dx
                        tx1 = x1 + dx
                        if ty0 < 0 or ty1 > ny or tx0 < 0 or tx1 > nx:
                            continue
                        candidate = f2[ty0:ty1, tx0:tx1]
                        cost = np.mean((template - candidate) ** 2)
                        if cost < best_cost:
                            best_cost = cost
                            best_dy, best_dx = dy, dx

                u[y0:y1, x0:x1] = best_dx
                v[y0:y1, x0:x1] = best_dy

        return u, v

    def smooth_flow(
        self,
        u: np.ndarray,
        v: np.ndarray,
        kernel_size: int = 21,
        sigma: float = 2.0,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Smooth the flow field using a Gaussian filter."""
        from scipy.ndimage import gaussian_filter
        u_s = gaussian_filter(np.nan_to_num(u), sigma=sigma, mode="nearest")
        v_s = gaussian_filter(np.nan_to_num(v), sigma=sigma, mode="nearest")
        return u_s, v_s
