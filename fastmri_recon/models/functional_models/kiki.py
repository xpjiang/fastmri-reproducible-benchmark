"""KIKI network."""
import tensorflow as tf
from tensorflow.keras.layers import Input, Lambda
from tensorflow.keras.models import Model

from ..training.compile import default_model_compile
from ..utils.complex import conv2d_complex
from ..utils.data_consistency import MultiplyScalar, enforce_kspace_data_consistency
from ..utils.fastmri_format import tf_fastmri_format
from ..utils.fourier import  tf_unmasked_adj_op, tf_unmasked_op


def kiki_net(input_size=(640, None, 1), n_cascade=2, n_convs=5, n_filters=16, noiseless=True, lr=1e-3, fastmri=True, activation='relu'):
    r"""This net is a sequence of of convolution blocks in both the direct and indirect space

    The original network is described in [E2017]. It also features a data consistency
    layer before performing convolutions in the indirect space (kspace).

    Parameters:
    input_size (tuple): the size of your input kspace, default to (640, None, 1)
    n_cascade (int): number of cascades, defaults to 2 like in paper
    n_convs (int): number of convolution in convolution blocks (N_I in paper), defaults to 5
    n_filters (int): number of filters in a convolution, defaults to 16
    noiseless (bool): whether the data consistency has to be done in a noiseless
        manner. If noiseless is `False`, the noise level is learned (i.e. lambda
        in paper, is learned). Defaults to `True`.
    lr (float): learning rate, defaults to 1e-3
    fastmri (bool): whether to put the final image in fastMRI format, defaults
        to True (i.e. image will be cropped to 320, 320)
    activation (str or function): see https://keras.io/activations/ for info

    Returns:
    keras.models.Model: the KIKI net model, compiled
    """
    mask_shape = input_size[:-1]
    kspace_input = Input(input_size, dtype='complex64', name='kspace_input')
    mask = Input(mask_shape, dtype='complex64', name='mask_input')

    kspace = kspace_input
    multiply_scalar = MultiplyScalar()
    for i in range(n_cascade):
        # K-net
        kspace = conv2d_complex(kspace, n_filters, n_convs, output_shape=input_size, res=False, activation=activation, last_kernel_size=1)
        image = Lambda(tf_unmasked_adj_op, output_shape=input_size, name='ifft_simple_{i}'.format(i=i+1))(kspace)
        # residual convolution (I-net)
        image = conv2d_complex(image, n_filters, n_convs, output_shape=input_size, res=True, activation=activation, last_kernel_size=1)
        # data consistency layer
        kspace = Lambda(tf_unmasked_op, output_shape=input_size, name='fft_simple_{i}'.format(i=i+1))(image)
        kspace = enforce_kspace_data_consistency(kspace, kspace_input, mask, input_size, multiply_scalar, noiseless)

    image = Lambda(tf_unmasked_adj_op, output_shape=input_size, name='ifft_simple')(kspace)
    # module and crop of image
    if fastmri:
        image = tf_fastmri_format(image)
    else:
        image = Lambda(tf.math.abs)(image)
    model = Model(inputs=[kspace_input, mask], outputs=image)

    default_model_compile(model, lr)

    return model
