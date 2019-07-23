import glob
import time

import h5py
from keras.utils import Sequence
import numpy as np

from fourier import FFT2
from utils import crop_center, gen_mask, normalize, normalize_instance

def from_test_file_to_mask_and_kspace(filename):
    with  h5py.File(filename) as h5_obj:
        masks = h5_obj['mask'][()]
        kspaces = h5_obj['kspace'][()]
        return masks, kspaces



def from_train_file_to_image_and_kspace(filename):
    with h5py.File(filename) as h5_obj:
        images = h5_obj['reconstruction_esc'][()]
        kspaces = h5_obj['kspace'][()]
        return images, kspaces


def from_file_to_kspace(filename):
    with h5py.File(filename) as h5_obj:
        kspaces = h5_obj['kspace'][()]
        return kspaces

def fft(image):
    fourier_op = FFT2(np.ones_like(image))
    kspace = fourier_op.op(image)
    return kspace

def ifft(kspace):
    fourier_op = FFT2(np.ones_like(kspace))
    image = fourier_op.adj_op(kspace)
    return image

def zero_filled(kspace):
    fourier_op = FFT2(np.ones_like(kspace))
    im_recon = np.abs(fourier_op.adj_op(kspace))
    im_cropped = crop_center(im_recon, 320)
    return im_cropped


class fastMRI2DSequence(Sequence):
    train_modes = ('training', 'validation')

    def __init__(self, path, mode='training', af=4, norm=False):
        self.path = path
        self.mode = mode
        self.af = af
        self.norm = norm

        self.filenames = glob.glob(path + '*.h5')
        if not self.filenames:
            raise ValueError('No h5 files at path {}'.format(path))
        self.filenames.sort()
        if mode == 'testing':
            af_filenames = list()
            for filename in self.filenames:
                mask, _ = from_test_file_to_mask_and_kspace(filename)
                mask_af = len(mask) / sum(mask)
                if af == 4 and mask_af < 5.5 or af == 8 and mask_af > 8:
                    af_filenames.append(filename)
            self.filenames = af_filenames


    def __len__(self):
        """From fastMRI paper"""
        return len(self.filenames)

    def __getitem__(self, idx):
        filename = self.filenames[idx]
        if self.mode in type(self).train_modes:
            return self.get_item_train(filename)
        else:
            return self.get_item_test(filename)


    def get_item_train(self, filename):
        pass

    def get_item_test(self, filename):
        pass


class ZeroPadded2DSequence(fastMRI2DSequence):
    pad = 644
    def get_item_train(self, filename):
        images, kspaces = from_train_file_to_image_and_kspace(filename)
        mask = gen_mask(kspaces[0], accel_factor=self.af)
        fourier_mask = np.repeat(mask.astype(np.float), kspaces[0].shape[0], axis=0)
        img_batch = list()
        z_kspace_batch = list()
        to_pad = type(self).pad - kspaces.shape[2]
        pad_seq = [(0, 0), (to_pad // 2, to_pad // 2)]
        for kspace, image in zip(kspaces, images):
            zero_filled_rec = ifft(kspace * fourier_mask)
            if self.norm:
                zero_filled_rec, mean, std = normalize_instance(zero_filled_rec, eps=1e-11)
                image = normalize(image, mean, std, eps=1e-11)
            zero_filled_rec = np.pad(zero_filled_rec, pad_seq, mode='constant')
            z_kspace = fft(zero_filled_rec)
            z_kspace = z_kspace[:, :, None]
            z_kspace_batch.append(z_kspace)
            image = np.pad(image, pad_seq, mode='constant')
            image = image[..., None]
            img_batch.append(image)
        z_kspace_batch = np.array(z_kspace_batch)
        img_batch = np.array(img_batch)
        return (z_kspace_batch, img_batch)


    def get_item_test(self, filename):
        _, kspaces = from_test_file_to_mask_and_kspace(filename)
        z_kspace_batch = list()
        means = list()
        stddevs = list()
        to_pad = type(self).pad - kspaces.shape[2]
        pad_seq = [(0, 0), (to_pad // 2, to_pad // 2)]
        for kspace in kspaces:
            zero_filled_rec = ifft(kspace)
            if self.norm:
                zero_filled_rec, mean, std = normalize_instance(zero_filled_rec, eps=1e-11)
                means.append(mean)
                stddevs.append(std)
            zero_filled_rec = np.pad(zero_filled_rec, pad_seq, mode='constant')
            z_kspace = fft(zero_filled_rec)
            z_kspace = z_kspace[:, :, None]
            z_kspace_batch.append(z_kspace)
        z_kspace_batch = np.array(z_kspace_batch)
        if self.norm:
            return z_kspace_batch, means, stddevs
        else:
            return z_kspace_batch


class ZeroFilled2DSequence(fastMRI2DSequence):
    def get_item_train(self, filename):
        images, kspaces = from_train_file_to_image_and_kspace(filename)
        mask = gen_mask(kspaces[0], accel_factor=self.af)
        fourier_mask = np.repeat(mask.astype(np.float), kspaces[0].shape[0], axis=0)
        img_batch = list()
        zero_img_batch = list()
        for kspace, image in zip(kspaces, images):
            zero_filled_rec = zero_filled(kspace * fourier_mask)
            if self.norm:
                zero_filled_rec, mean, std = normalize_instance(zero_filled_rec, eps=1e-11)
                image = normalize(image, mean, std, eps=1e-11)
            zero_filled_rec = zero_filled_rec[:, :, None]
            zero_img_batch.append(zero_filled_rec)
            image = image[..., None]
            img_batch.append(image)
        zero_img_batch = np.array(zero_img_batch)
        img_batch = np.array(img_batch)
        return (zero_img_batch, img_batch)


    def get_item_test(self, filename):
        _, kspaces = from_test_file_to_mask_and_kspace(filename)
        zero_img_batch = list()
        means = list()
        stddevs = list()
        for kspace in kspaces:
            zero_filled_rec = zero_filled(kspace)
            if self.norm:
                zero_filled_rec, mean, std = normalize_instance(zero_filled_rec, eps=1e-11)
                means.append(mean)
                stddevs.append(std)
            zero_filled_rec = zero_filled_rec[:, :, None]
            zero_img_batch.append(zero_filled_rec)
        zero_img_batch = np.array(zero_img_batch)
        if self.norm:
            return zero_img_batch, means, stddevs
        else:
            return zero_img_batch