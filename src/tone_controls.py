"""Three broad tone controls over an existing EQ curve, preserving its detail."""

import math


def tone_weights(frequency: float) -> tuple[float, float, float]:
    def ramp(low: float, high: float) -> float:
        return max(
            0.0, min(1.0, math.log(max(frequency, 1.0) / low) / math.log(high / low))
        )

    return (
        1.0 - ramp(100, 700),
        ramp(200, 1500) * (1.0 - ramp(1500, 6000)),
        ramp(2500, 10000),
    )


def split_tone_curve(bands: list[dict]) -> tuple[list[float], list[float]]:
    """Fit three controls and retain the residual so merely opening Simple is lossless."""
    weights = [tone_weights(b["frequency"]) for b in bands]
    matrix = [
        [sum(w[i] * w[j] for w in weights) for j in range(3)]
        + [sum(w[i] * b["gain"] for w, b in zip(weights, bands, strict=True))]
        for i in range(3)
    ]
    for i in range(3):
        pivot = max(range(i, 3), key=lambda row: abs(matrix[row][i]))
        matrix[i], matrix[pivot] = matrix[pivot], matrix[i]
        if abs(matrix[i][i]) < 1e-9:
            return [0.0] * 3, [float(b["gain"]) for b in bands]
        divisor = matrix[i][i]
        matrix[i] = [v / divisor for v in matrix[i]]
        for row in range(3):
            if row != i:
                factor = matrix[row][i]
                matrix[row] = [
                    v - factor * p for v, p in zip(matrix[row], matrix[i], strict=True)
                ]
    controls = [(round(max(-12.0, min(12.0, matrix[i][3])), 1) or 0.0) for i in range(3)]
    residual = [
        b["gain"] - sum(w * c for w, c in zip(ws, controls, strict=True))
        for b, ws in zip(bands, weights, strict=True)
    ]
    return controls, residual


def apply_tone_curve(
    bands: list[dict], controls: list[float], residual: list[float]
) -> list[dict]:
    return [
        {
            "frequency": b["frequency"],
            "gain": round(
                max(
                    -12.0,
                    min(
                        12.0,
                        rest
                        + sum(
                            w * c
                            for w, c in zip(
                                tone_weights(b["frequency"]), controls, strict=True
                            )
                        ),
                    ),
                ),
                3,
            ),
        }
        for b, rest in zip(bands, residual, strict=True)
    ]
