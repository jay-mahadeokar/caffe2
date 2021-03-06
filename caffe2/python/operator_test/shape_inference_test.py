import unittest

import numpy as np
from caffe2.proto import caffe2_pb2
from caffe2.python import core, workspace, test_util, cnn


class TestShapeInference(test_util.TestCase):

    def testShapeInferenceSimpleFC(self):
        m = cnn.CNNModelHelper()

        m.FC("data", "fc1", dim_in=96, dim_out=32)
        m.FC("fc1", "fc2", dim_in=32, dim_out=55)

        (shapes, types) = workspace.InferShapesAndTypes(
            [m.param_init_net, m.net],
            {'data': [64, 96]}
        )

        self.assertEquals(shapes['data'], [64, 96])
        self.assertEquals(shapes['fc1_w'], [32, 96])
        self.assertEquals(shapes['fc1_b'], [32])
        self.assertEquals(shapes['fc1'], [64, 32])
        self.assertEquals(shapes['fc2_w'], [55, 32])
        self.assertEquals(shapes['fc2_b'], [55])
        self.assertEquals(shapes['fc2'], [64, 55])

    def testShapeInferencDistances(self):
        model = cnn.CNNModelHelper()
        model.SquaredL2Distance(["x", "y"], "zsq")
        model.CosineSimilarity(["x", "y"], "zcos")
        model.DotProduct(["x", "y"], "zdot")

        workspace.FeedBlob("x", np.random.rand(10).astype(np.float32))
        workspace.FeedBlob("y", np.random.rand(10).astype(np.float32))
        self.InferTensorRunAndCompare(model)

    def testShapeInferenceConvNet(self):
        model = cnn.CNNModelHelper(name="convtest", order="NCHW")
        model.Conv("data", 'conv1', 3, 64,
                   weight_init=("MSRAFill", {}), kernel=7,
                   stride=2, pad=3, no_bias=0)
        model.SpatialBN('conv1', 'conv1_spatbn_relu', 64, epsilon=1e-3)
        model.Relu('conv1_spatbn_relu', 'conv1_spatbn_relu')
        model.MaxPool('conv1_spatbn_relu', 'pool1', kernel=3, stride=2)
        model.FC('pool1', 'fc', dim_in=(64 * 56 * 56), dim_out=100)
        model.Sigmoid('fc', 'fc_sigm')
        model.Softmax('fc_sigm', 'softmax')

        workspace.FeedBlob(
            "data",
            np.random.rand(16, 3, 227, 227).astype(np.float32),
        )
        # Then do automatic comparison test: run the next once to
        # initialize everything
        self.InferTensorRunAndCompare(model)

    def testShapeInferenceTranspose(self):
        model = cnn.CNNModelHelper()

        workspace.FeedBlob(
            "tensor",
            np.random.rand(4, 2, 3, 3, 5).astype(np.float32)
        )

        # Testing with axes undefined
        model.Transpose(
            ["tensor"],
            "transpose",
        )
        self.InferTensorRunAndCompare(model)

        # Testing with axes defined
        model.Transpose(
            ["tensor"],
            "transpose",
            axes=np.random.permutation(5)
        )
        self.InferTensorRunAndCompare(model)

    def InferTensorRunAndCompare(self, model):
        '''
        Runs shape inference, and then the model to check
        that the inferred shapes agree with the actual ones
        '''
        (shapes, types) = workspace.InferShapesAndTypes(
            [model.param_init_net, model.net],
        )

        # .. Create net
        workspace.RunNetOnce(model.param_init_net)
        workspace.CreateNet(model.net)
        workspace.RunNet(model.Proto().name)

        # ... and then check the shapes mismatch
        correct_shapes = {}
        correct_types = {}
        for b in workspace.Blobs():
            arr = workspace.FetchBlob(b)
            correct_shapes[b] = arr.shape
            if type(arr) is np.ndarray:
                if arr.dtype == np.dtype('float64'):
                    correct_types[b] = caffe2_pb2.TensorProto.DOUBLE
                elif arr.dtype == np.dtype('float32'):
                    correct_types[b] = caffe2_pb2.TensorProto.FLOAT
                elif arr.dtype == np.dtype('int32'):
                    correct_types[b] = caffe2_pb2.TensorProto.INT32
                elif arr.dtype == np.dtype('int64'):
                    correct_types[b] = caffe2_pb2.TensorProto.INT64
                else:
                    correct_types[b] = "unknown {}".format(np.dtype)
            else:
                correct_types[b] = str(type(arr))

        for b in correct_shapes:
            self.assertTrue(
                np.array_equal(
                    np.array(shapes[b]).astype(np.int32),
                    np.array(correct_shapes[b]).astype(np.int32)
                ),
                "Shape {} mismatch: {} vs. {}".format(
                    b, shapes[b], correct_shapes[b]
                )
            )
            self.assertFalse(
                b not in types and b in correct_types,
                "Type for {} not defined".format(b),
            )
            self.assertEqual(
                types[b],
                correct_types[b],
                "Type {} mismatch: {} vs. {}".format(
                    b, types[b], correct_types[b],
                )
            )



if __name__ == "__main__":
    import unittest
    unittest.main()
