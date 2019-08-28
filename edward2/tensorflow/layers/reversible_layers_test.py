# coding=utf-8
# Copyright 2019 The Edward2 Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for reversible layers."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from absl.testing import parameterized
import edward2 as ed
import numpy as np
import tensorflow as tf1
import tensorflow.compat.v2 as tf

reversible = ed.layers.reversible_layers
tfe = tf1.contrib.eager


class ReversibleLayersTest(parameterized.TestCase, tf.test.TestCase):

  @parameterized.parameters(
      (False,),
      (True,),
  )
  @tfe.run_test_in_graph_and_eager_modes
  def testDiscreteAutoregressiveFlowCall(self, loc_only):
    batch_size = 3
    vocab_size = 79
    length = 5
    if loc_only:
      units = vocab_size
      network = reversible.MADE(units, [])
    else:
      units = 2 * vocab_size
      mask = tf.reshape([0] * vocab_size + [-1e10] + [0] * (vocab_size - 1),
                        [1, 1, 2 * vocab_size])
      network_ = reversible.MADE(units, [])
      network = lambda inputs, **kwargs: mask + network_(inputs, **kwargs)
    inputs = np.random.randint(0, vocab_size - 1, size=(batch_size, length))
    inputs = tf.one_hot(inputs, depth=vocab_size, dtype=tf.float32)
    layer = reversible.DiscreteAutoregressiveFlow(network, 1.)
    outputs = layer(inputs)
    self.evaluate(tf1.global_variables_initializer())
    outputs_val = self.evaluate(outputs)
    self.assertEqual(outputs_val.shape, (batch_size, length, vocab_size))
    self.assertAllGreaterEqual(outputs_val, 0)
    self.assertAllLessEqual(outputs_val, vocab_size - 1)

  @parameterized.parameters(
      (False,),
      (True,),
  )
  @tfe.run_test_in_graph_and_eager_modes
  def testDiscreteAutoregressiveFlowSample(self, loc_only):
    batch_size = 5
    length = 2
    vocab_size = 2
    if loc_only:
      units = vocab_size
      network = reversible.MADE(units, [])
    else:
      units = 2 * vocab_size
      mask = tf.reshape([0] * vocab_size + [-1e10] + [0] * (vocab_size - 1),
                        [1, 1, 2 * vocab_size])
      network_ = reversible.MADE(units, [])
      network = lambda inputs, **kwargs: mask + network_(inputs, **kwargs)
    layer = reversible.DiscreteAutoregressiveFlow(network, 1.)
    logits = tf.tile(tf.random.normal([length, vocab_size])[tf.newaxis],
                     [batch_size, 1, 1])
    base = ed.OneHotCategorical(logits=logits, dtype=tf.float32)
    outputs = layer(base)
    _ = outputs.value  # need to do this to instantiate tf.variables
    self.evaluate(tf1.global_variables_initializer())
    res = self.evaluate(outputs)
    self.assertEqual(res.shape, (batch_size, length, vocab_size))
    self.assertAllGreaterEqual(res, 0)
    self.assertAllLessEqual(res, vocab_size - 1)

  @parameterized.parameters(
      (False,),
      (True,),
  )
  @tfe.run_test_in_graph_and_eager_modes
  def testDiscreteAutoregressiveFlowInverse(self, loc_only):
    batch_size = 2
    vocab_size = 79
    length = 5
    if loc_only:
      units = vocab_size
      network = reversible.MADE(units, [])
    else:
      units = 2 * vocab_size
      mask = tf.reshape([0] * vocab_size + [-1e10] + [0] * (vocab_size - 1),
                        [1, 1, 2 * vocab_size])
      network_ = reversible.MADE(units, [])
      network = lambda inputs, **kwargs: mask + network_(inputs, **kwargs)
    inputs = np.random.randint(0, vocab_size - 1, size=(batch_size, length))
    inputs = tf.one_hot(inputs, depth=vocab_size, dtype=tf.float32)
    layer = reversible.DiscreteAutoregressiveFlow(network, 1.)
    rev_fwd_inputs = layer.reverse(layer(inputs))
    fwd_rev_inputs = layer(layer.reverse(inputs))
    self.evaluate(tf1.global_variables_initializer())
    inputs_val, rev_fwd_inputs_val, fwd_rev_inputs_val = self.evaluate(
        [inputs, rev_fwd_inputs, fwd_rev_inputs])
    self.assertAllClose(inputs_val, rev_fwd_inputs_val, rtol=1e-4, atol=1e-4)
    self.assertAllClose(inputs_val, fwd_rev_inputs_val, rtol=1e-4, atol=1e-4)

  @parameterized.parameters(
      (False,),
      (True,),
  )
  @tfe.run_test_in_graph_and_eager_modes
  def testDiscreteAutoregressiveFlowRandomVariable(self, loc_only):
    batch_size = 2
    length = 4
    vocab_size = 5
    if loc_only:
      units = vocab_size
      network = reversible.MADE(units, [])
    else:
      units = 2 * vocab_size
      mask = tf.reshape([0] * vocab_size + [-1e10] + [0] * (vocab_size - 1),
                        [1, 1, 2 * vocab_size])
      network_ = reversible.MADE(units, [])
      network = lambda inputs, **kwargs: mask + network_(inputs, **kwargs)
    base = ed.OneHotCategorical(logits=tf.random.normal([batch_size,
                                                         length,
                                                         vocab_size]),
                                dtype=tf.float32)
    flow = reversible.DiscreteAutoregressiveFlow(network, 1.)
    flow_rv = flow(base)
    self.assertEqual(flow_rv.dtype, tf.float32)

    self.evaluate(tf1.global_variables_initializer())
    res = self.evaluate(flow_rv)
    self.assertEqual(res.shape, (batch_size, length, vocab_size))
    self.assertAllGreaterEqual(res, 0)
    self.assertAllLessEqual(res, vocab_size - 1)

    inputs = np.random.randint(0, vocab_size - 1, size=(batch_size, length))
    inputs = tf.one_hot(inputs, depth=vocab_size, dtype=tf.float32)
    outputs = flow(inputs)
    rev_outputs = flow.reverse(outputs)
    inputs_val, rev_outputs_val = self.evaluate([inputs, rev_outputs])
    self.assertAllClose(inputs_val, rev_outputs_val)

    inputs_log_prob = base.distribution.log_prob(inputs)
    outputs_log_prob = flow_rv.distribution.log_prob(outputs)
    res1, res2 = self.evaluate([inputs_log_prob, outputs_log_prob])
    self.assertEqual(res1.shape, (batch_size, length))
    self.assertAllClose(res1, res2)

  @parameterized.parameters(
      (False,),
      (True,),
  )
  def testDiscreteAutoregressiveFlowReverseGradients(self, loc_only):
    batch_size = 2
    length = 4
    vocab_size = 2
    if loc_only:
      units = vocab_size
      network_ = reversible.MADE(units, [16, 16])
      network = network_
    else:
      units = 2 * vocab_size
      network_ = reversible.MADE(units, [16, 16])
      mask = tf.reshape([0] * vocab_size + [-1e10] + [0] * (vocab_size - 1),
                        [1, 1, 2 * vocab_size])
      network = lambda inputs, **kwargs: mask + network_(inputs, **kwargs)
    base = ed.OneHotCategorical(
        logits=tf.random.normal([batch_size, length, vocab_size]))
    flow = reversible.DiscreteAutoregressiveFlow(network, 1.)
    flow_rv = flow(base)
    features = np.random.randint(0, vocab_size - 1, size=(batch_size, length))
    features = tf.one_hot(features, depth=vocab_size, dtype=tf.float32)
    loss = tf.reduce_sum(tf.nn.softmax_cross_entropy_with_logits(
        labels=flow.reverse(features), logits=flow_rv.distribution.base.logits))
    grads = tf1.gradients(loss, network_.weights)
    self.evaluate(tf1.global_variables_initializer())
    _ = self.evaluate(grads)
    for grad in grads:
      self.assertIsNotNone(grad)

  @tfe.run_test_in_graph_and_eager_modes
  def testOneHotAddExactHard(self):
    inputs = tf.constant([[0., 1., 0.],
                          [0., 0., 1.]])
    shift = tf.constant([[0., 1., 0.],
                         [1., 0., 0.]])

    outputs = reversible.one_hot_add(inputs, shift)
    outputs_val = self.evaluate(outputs)
    self.assertAllClose(outputs_val,
                        np.array([[0., 0., 1.],
                                  [0., 0., 1.]], dtype=np.float32),
                        rtol=1e-4, atol=1e-4)

  @tfe.run_test_in_graph_and_eager_modes
  def testOneHotMinusExactHard(self):
    inputs = tf.constant([[0., 1., 0.],
                          [0., 0., 1.]])
    shift = tf.constant([[0., 1., 0.],
                         [1., 0., 0.]])

    outputs = reversible.one_hot_minus(inputs, shift)
    outputs_val = self.evaluate(outputs)
    self.assertAllEqual(outputs_val, np.array([[1., 0., 0.],
                                               [0., 0., 1.]], dtype=np.float32))

  @tfe.run_test_in_graph_and_eager_modes
  def testOneHotMultiplyExactHard(self):
    inputs = tf.constant([[0., 1., 0.],
                          [0., 0., 1.]])
    scale = tf.constant([[0., 1., 0.],
                         [0., 0., 1.]])

    outputs = reversible.one_hot_multiply(inputs, scale)
    outputs_val = self.evaluate(outputs)
    self.assertAllEqual(outputs_val, np.array([[0., 1., 0.],
                                               [0., 1., 0.]], dtype=np.float32))

  @tfe.run_test_in_graph_and_eager_modes
  def testOneHotAddExactSoft(self):
    inputs = tf.constant([[0., 1., 0.],
                          [0., 0., 1.]])
    shift = tf.constant([[0.1, 0.6, 0.3],
                         [0.2, 0.4, 0.4]])

    outputs = reversible.one_hot_add(inputs, shift)

    shift_zero = inputs
    shift_one = np.array([[0., 0., 1.],
                          [1., 0., 0.]])
    shift_two = np.array([[1., 0., 0.],
                          [0., 1., 0.]])
    expected_outputs = (shift[..., 0][..., tf.newaxis] * shift_zero +
                        shift[..., 1][..., tf.newaxis] * shift_one +
                        shift[..., 2][..., tf.newaxis] * shift_two)

    actual_outputs_val, expected_outputs_val = self.evaluate([
        outputs, expected_outputs])
    self.assertAllClose(actual_outputs_val, expected_outputs_val)

  @tfe.run_test_in_graph_and_eager_modes
  def testOneHotMinusExactSoft(self):
    inputs = tf.constant([[0., 1., 0.],
                          [0., 0., 1.]])
    shift = tf.constant([[0.1, 0.6, 0.3],
                         [0.2, 0.4, 0.4]])

    outputs = reversible.one_hot_minus(inputs, shift)

    shift_zero = inputs
    shift_one = np.array([[1., 0., 0.],
                          [0., 1., 0.]])
    shift_two = np.array([[0., 0., 1.],
                          [1., 0., 0.]])
    expected_outputs = (shift[..., 0][..., tf.newaxis] * shift_zero +
                        shift[..., 1][..., tf.newaxis] * shift_one +
                        shift[..., 2][..., tf.newaxis] * shift_two)

    actual_outputs_val, expected_outputs_val = self.evaluate([
        outputs, expected_outputs])
    self.assertAllEqual(actual_outputs_val, expected_outputs_val)

  @tfe.run_test_in_graph_and_eager_modes
  def testOneHotMultiplyExactSoft(self):
    inputs = tf.constant([[0., 1., 0.],
                          [0., 0., 1.]])
    scale = tf.constant([[0.1, 0.6, 0.3],
                         [0.2, 0.4, 0.4]])

    outputs = reversible.one_hot_multiply(inputs, scale)

    scale_zero = np.array([[0., 0., 0.],
                           [0., 0., 0.]])
    scale_one = inputs
    scale_two = np.array([[0., 0., 1.],
                          [0., 1., 0.]])
    expected_outputs = (scale[..., 0][..., tf.newaxis] * scale_zero +
                        scale[..., 1][..., tf.newaxis] * scale_one +
                        scale[..., 2][..., tf.newaxis] * scale_two)

    actual_outputs_val, expected_outputs_val = self.evaluate([
        outputs, expected_outputs])
    self.assertAllEqual(actual_outputs_val, expected_outputs_val)

  @parameterized.parameters(
      (reversible.one_hot_add,),
      (reversible.one_hot_minus,),
  )
  @tfe.run_test_in_graph_and_eager_modes
  def testOneHotAddShapeHard(self, one_hot_add_fn):
    batch_size = 2
    length = 4
    vocab_size = 5
    inputs = tf.random.uniform(
        [batch_size, length], minval=0, maxval=vocab_size, dtype=tf.int32)
    inputs = tf.one_hot(inputs, depth=vocab_size, dtype=tf.float32)
    shift = tf.random.uniform(
        [batch_size, length], minval=0, maxval=vocab_size, dtype=tf.int32)
    shift = tf.one_hot(shift, depth=vocab_size)

    outputs = one_hot_add_fn(inputs, shift)
    outputs_val = self.evaluate(outputs)
    self.assertEqual(outputs_val.shape, (batch_size, length, vocab_size))

  @parameterized.parameters(
      (reversible.one_hot_add,),
      (reversible.one_hot_minus,),
  )
  @tfe.run_test_in_graph_and_eager_modes
  def testOneHotAddShapeSoft(self, one_hot_add_fn):
    batch_size = 2
    length = 4
    vocab_size = 5
    inputs = tf.random.uniform([batch_size, length, vocab_size])
    shift = tf.random.uniform([batch_size, length, vocab_size])

    outputs = one_hot_add_fn(inputs, shift)
    outputs_val = self.evaluate(outputs)
    self.assertEqual(outputs_val.shape, (batch_size, length, vocab_size))

  @tfe.run_test_in_graph_and_eager_modes
  def testMultiplicativeInverse(self):
    batch_size = 3
    vocab_size = 79
    length = 5
    inputs = np.random.randint(0, vocab_size - 1, size=(batch_size, length))
    one_hot_inputs = tf.one_hot(inputs, depth=vocab_size)

    one_hot_inv = reversible.multiplicative_inverse(one_hot_inputs, vocab_size)
    inv_inputs = tf.argmax(one_hot_inv, axis=-1)
    inputs_inv_inputs = tf.math.floormod(inputs * inv_inputs, vocab_size)
    inputs_inv_inputs_val = self.evaluate(inputs_inv_inputs)
    self.assertAllEqual(inputs_inv_inputs_val, np.ones((batch_size, length)))

  @tfe.run_test_in_graph_and_eager_modes
  def testDiscreteBipartiteFlowCall(self):
    batch_size = 3
    vocab_size = 79
    length = 5
    inputs = np.random.randint(0, vocab_size - 1, size=(batch_size, length))
    inputs = tf.one_hot(inputs, depth=vocab_size, dtype=tf.float32)
    layer = reversible.DiscreteBipartiteFlow(
        lambda inputs, **kwargs: tf.identity(inputs),
        mask=tf.random.uniform([length], minval=0, maxval=2, dtype=tf.int32),
        temperature=1.)
    outputs = layer(inputs)
    self.evaluate(tf1.global_variables_initializer())
    outputs_val = self.evaluate(outputs)
    self.assertEqual(outputs_val.shape, (batch_size, length, vocab_size))
    self.assertAllGreaterEqual(outputs_val, 0)
    self.assertAllLessEqual(outputs_val, vocab_size - 1)

  @tfe.run_test_in_graph_and_eager_modes
  def testDiscreteBipartiteFlowInverse(self):
    batch_size = 2
    vocab_size = 79
    length = 5
    inputs = np.random.randint(0, vocab_size - 1, size=(batch_size, length))
    inputs = tf.one_hot(inputs, depth=vocab_size, dtype=tf.float32)
    layer = reversible.DiscreteBipartiteFlow(
        lambda inputs, **kwargs: tf.identity(inputs),
        mask=tf.random.uniform([length], minval=0, maxval=2, dtype=tf.int32),
        temperature=1.)
    rev_fwd_inputs = layer.reverse(layer(inputs))
    fwd_rev_inputs = layer(layer.reverse(inputs))
    self.evaluate(tf1.global_variables_initializer())
    inputs_val, rev_fwd_inputs_val, fwd_rev_inputs_val = self.evaluate(
        [inputs, rev_fwd_inputs, fwd_rev_inputs])
    self.assertAllClose(inputs_val, rev_fwd_inputs_val)
    self.assertAllClose(inputs_val, fwd_rev_inputs_val)

  @tfe.run_test_in_graph_and_eager_modes
  def testSinkhornAutoregressiveFlowCall(self):
    batch_size = 3
    vocab_size = 79
    length = 5
    units = vocab_size ** 2
    inputs = np.random.randint(0, vocab_size - 1, size=(batch_size, length))
    inputs = tf.one_hot(inputs, depth=vocab_size, dtype=tf.float32)
    layer = reversible.SinkhornAutoregressiveFlow(
        reversible.MADE(units, []), 1.)
    outputs = layer(inputs)
    self.evaluate(tf1.global_variables_initializer())
    outputs_val = self.evaluate(outputs)
    self.assertEqual(outputs_val.shape, (batch_size, length, vocab_size))
    self.assertAllGreaterEqual(outputs_val, 0)
    self.assertAllLessEqual(outputs_val, vocab_size - 1)

  @tfe.run_test_in_graph_and_eager_modes
  def testDiscreteSinkhornFlowInverse(self):
    batch_size = 2
    vocab_size = 79
    length = 5
    units = vocab_size ** 2
    inputs = np.random.randint(0, vocab_size - 1, size=(batch_size, length))
    inputs = tf.one_hot(inputs, depth=vocab_size, dtype=tf.float32)
    layer = reversible.SinkhornAutoregressiveFlow(
        reversible.MADE(units, []), 1.)
    rev_fwd_inputs = layer.reverse(layer(inputs))
    fwd_rev_inputs = layer(layer.reverse(inputs))
    self.evaluate(tf1.global_variables_initializer())
    inputs_val, rev_fwd_inputs_val, fwd_rev_inputs_val = self.evaluate(
        [inputs, rev_fwd_inputs, fwd_rev_inputs])
    self.assertAllEqual(inputs_val, rev_fwd_inputs_val)
    self.assertAllEqual(inputs_val, fwd_rev_inputs_val)

  @tfe.run_test_in_graph_and_eager_modes
  def testApproximatelyStochastic(self):
    rng = np.random.RandomState(0)
    tf.random.set_seed(1)
    for dims in [2, 5, 10]:
      for batch_size in [1, 2, 10]:
        log_alpha = rng.randn(batch_size, dims, dims)
        result = reversible.sinkhorn(log_alpha)
        result_val = self.evaluate(result)
        self.assertAllClose(np.sum(result_val, 1),
                            np.tile([1.0], (batch_size, dims)),
                            atol=1e-3)
        self.assertAllClose(np.sum(result_val, 2),
                            np.tile([1.0], (batch_size, dims)),
                            atol=1e-3)

  def test_soft_to_hard_permutation(self):
    """The solution of the matching for the identity matrix is range(N)."""
    dims = 10
    identity = np.eye(dims)
    result_matching = reversible.soft_to_hard_permutation(identity)
    result_matching_val = self.evaluate(result_matching)
    self.assertAllEqual(result_matching_val[0], np.eye(dims))

  @tfe.run_test_in_graph_and_eager_modes
  def testActNorm(self):
    np.random.seed(83243)
    batch_size = 25
    length = 15
    channels = 4
    inputs = 3. + 0.8 * np.random.randn(batch_size, length, channels)
    inputs = tf.cast(inputs, tf.float32)
    layer = reversible.ActNorm()
    outputs = layer(inputs)
    mean, variance = tf.nn.moments(outputs, axes=[0, 1])
    self.evaluate(tf1.global_variables_initializer())
    mean_val, variance_val = self.evaluate([mean, variance])
    self.assertAllClose(mean_val, np.zeros(channels), atol=1e-3)
    self.assertAllClose(variance_val, np.ones(channels), atol=1e-3)

    inputs = 3. + 0.8 * np.random.randn(batch_size, length, channels)
    inputs = tf.cast(inputs, tf.float32)
    outputs = layer(inputs)
    mean, variance = tf.nn.moments(outputs, axes=[0, 1])
    self.evaluate(tf1.global_variables_initializer())
    mean_val, variance_val = self.evaluate([mean, variance])
    self.assertAllClose(mean_val, np.zeros(channels), atol=0.25)
    self.assertAllClose(variance_val, np.ones(channels), atol=0.25)

  @tfe.run_test_in_graph_and_eager_modes
  def testMADELeftToRight(self):
    np.random.seed(83243)
    batch_size = 2
    length = 3
    channels = 1
    units = 5
    network = reversible.MADE(units, [4], activation=tf.nn.relu)
    inputs = tf.zeros([batch_size, length, channels])
    outputs = network(inputs)

    num_weights = sum([np.prod(weight.shape) for weight in network.weights])
    # Disable lint error for open-source. pylint: disable=g-generic-assert
    self.assertEqual(len(network.weights), 4)
    # pylint: enable=g-generic-assert
    self.assertEqual(num_weights, (3*1*4 + 4) + (4*3*5 + 3*5))

    self.evaluate(tf1.global_variables_initializer())
    outputs_val = self.evaluate(outputs)
    self.assertAllEqual(outputs_val[:, 0, :], np.zeros((batch_size, units)))
    self.assertEqual(outputs_val.shape, (batch_size, length, units))

  @tfe.run_test_in_graph_and_eager_modes
  def testMADERightToLeft(self):
    np.random.seed(1328)
    batch_size = 2
    length = 3
    channels = 5
    units = 1
    network = reversible.MADE(units, [4, 3],
                              input_order='right-to-left',
                              activation=tf.nn.relu,
                              use_bias=False)
    inputs = tf.zeros([batch_size, length, channels])
    outputs = network(inputs)

    num_weights = sum([np.prod(weight.shape) for weight in network.weights])
    # Disable lint error for open-source. pylint: disable=g-generic-assert
    self.assertEqual(len(network.weights), 3)
    # pylint: enable=g-generic-assert
    self.assertEqual(num_weights, 3*5*4 + 4*3 + 3*3*1)

    self.evaluate(tf1.global_variables_initializer())
    outputs_val = self.evaluate(outputs)
    self.assertAllEqual(outputs_val[:, -1, :], np.zeros((batch_size, units)))
    self.assertEqual(outputs_val.shape, (batch_size, length, units))

  @tfe.run_test_in_graph_and_eager_modes
  def testMADENoHidden(self):
    np.random.seed(532)
    batch_size = 2
    length = 3
    channels = 5
    units = 4
    network = reversible.MADE(units, [], input_order='left-to-right')
    inputs = tf.zeros([batch_size, length, channels])
    outputs = network(inputs)

    num_weights = sum([np.prod(weight.shape) for weight in network.weights])
    # Disable lint error for open-source. pylint: disable=g-generic-assert
    self.assertEqual(len(network.weights), 2)
    # pylint: enable=g-generic-assert
    self.assertEqual(num_weights, 3*5*3*4 + 3*4)

    self.evaluate(tf1.global_variables_initializer())
    outputs_val = self.evaluate(outputs)
    self.assertAllEqual(outputs_val[:, 0, :], np.zeros((batch_size, units)))
    self.assertEqual(outputs_val.shape, (batch_size, length, units))

  @tfe.run_test_in_graph_and_eager_modes
  def testTransformedRandomVariable(self):
    class Exp(tf.keras.layers.Layer):
      """Exponential activation function for reversible networks."""

      def __call__(self, inputs, *args, **kwargs):
        if not isinstance(inputs, ed.RandomVariable):
          return super(Exp, self).__call__(inputs, *args, **kwargs)
        return reversible.TransformedRandomVariable(inputs, self)

      def call(self, inputs):
        return tf.exp(inputs)

      def reverse(self, inputs):
        return tf.math.log(inputs)

      def log_det_jacobian(self, inputs):
        return -tf.math.log(inputs)

    x = ed.Normal(0., 1.)
    y = Exp()(x)
    y_sample = self.evaluate(y.distribution.sample())
    y_log_prob = self.evaluate(y.distribution.log_prob(y_sample))
    self.assertGreater(y_sample, 0.)
    self.assertTrue(np.isfinite(y_log_prob))


if __name__ == '__main__':
  tf.test.main()