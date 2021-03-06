import tensorflow as tf
from tensorflow.keras.models import Model

from ..utils.complex import to_complex
from ..utils.fastmri_format import tf_fastmri_format
from ..utils.fourier import IFFT
from ..utils.pad_for_pool import pad_for_pool


class MultiscaleComplex(Model):
    """A complex wrapper model around a multiscale float-valued network.

    This class allows to "decorate" a multiscale float-valued network, in a model
    accepting output of different input sizes and complex-valued.
    What it does is that it concatenates the real and imaginary of the input
    along the channel dimension, and recreates a complex-valued tensor as output
    using the same inverted logic.
    It also pads the input according to the number of scales present in the
    multiscale network to allow for handling images that do not have a power of
    2 shape.

    Parameters:
        model (tf.keras.models.Model): the multiscale float-valued network.
        res (bool): whether you want to add a residual connection to the network
            that only takes into account `n_output_channels` channel elements
            of the input. Defaults to False.
        n_scales (int): the number of scales in the multiscale float-valued
            network. Defaults to 0.
        n_output_channels (int): the number of expected output channels. Defaults
            to 1.
        fastmri_format (bool): whether we should format the output the knee
            fastMRI format, i.e. nslices x 320 x 320 x 1.
        **kwargs: keyword arguments to tf.keras.models.Model.
    """
    def __init__(
            self,
            model,
            res=False,
            n_scales=0,
            n_output_channels=1,
            fastmri_format=False,
            **kwargs,
        ):
        super(MultiscaleComplex, self).__init__(**kwargs)
        self.model = model
        self.res = res
        self.n_scales = n_scales
        self.n_output_channels = n_output_channels
        self.fastmri_format = fastmri_format
        if self.fastmri_format:
            self.adj_op = IFFT(masked=False, multicoil=False)

    def call(self, inputs):
        if not self.fastmri_format:
            outputs = inputs
        else:
            outputs = inputs[0]
            outputs = self.adj_op(outputs)
            # this is to be consistent for residual connexion
            inputs = outputs
        if self.n_scales > 0:
            outputs, n_pad = pad_for_pool(inputs, self.n_scales)
        outputs = tf.concat([tf.math.real(outputs), tf.math.imag(outputs)], axis=-1)
        outputs = self.model(outputs)
        outputs = to_complex(outputs, self.n_output_channels)
        if self.n_scales > 0:
            outputs = tf.cond(
                n_pad == 0,
                lambda: outputs,
                lambda: outputs[:, :, n_pad//2:-n_pad//2],
            )
        if self.res:
            outputs = inputs[..., :self.n_output_channels] + outputs
        if self.fastmri_format:
            outputs = tf_fastmri_format(outputs)
        return outputs
