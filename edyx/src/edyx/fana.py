import numpy as np
from scipy.ndimage import median_filter



# TODO where is the better version?
def despike_median(data, size, threshold=5):
    cutoff = np.std(data) * threshold
    filtered = median_filter(data, size=size)
    reject = np.abs(filtered-data) > cutoff
    despiked = np.copy(data)
    despiked[reject] = filtered[reject]
    return despiked
