import numpy as np
from pygrappa import cgrappa

from ...data.utils.crop import crop_center


def reco_grappa(kspace, af=4):
    n_slices, _, sx, sy = kspace.shape[:]
    if af == 4:
        n_acs = int(sy * 8 / 100)
    else:
        n_acs = int(sy * 4 / 100)
    ctr, pd = sy // 2, n_acs // 2
    calib = kspace[..., ctr-pd:ctr+pd].copy() # call copy()!
    recon = np.empty([n_slices, sx, sy], dtype=np.complex)
    for i in range(n_slices):
        recon[i] = cgrappa(kspace[i].astype(np.complex), calib[i].astype(np.complex), kernel_size=(5, 5), coil_axis=0)
    x_final = np.abs(recon)
    x_final = crop_center(x_final, 320)
    return x_final