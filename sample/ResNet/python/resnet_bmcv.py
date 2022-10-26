#===----------------------------------------------------------------------===#
#
# Copyright (C) 2022 Sophgo Technologies Inc.  All rights reserved.
#
# SOPHON-DEMO is licensed under the 2-Clause BSD License except for the
# third-party components.
#
#===----------------------------------------------------------------------===#
# -*- coding: utf-8 -*- 
import time
import os
import numpy as np
import argparse
import sophon.sail as sail
import logging
import glob
logging.basicConfig(level=logging.DEBUG)



class Resnet(object):
    def __init__(self, args):
        # load bmodel
        self.net = sail.Engine(args.bmodel, args.tpu_id, sail.IOMode.SYSO)
        logging.debug("load {} success!".format(args.bmodel))

        self.graph_name = self.net.get_graph_names()[0]
        self.input_names = self.net.get_input_names(self.graph_name)
        self.input_shapes = [self.net.get_input_shape(self.graph_name, name) for name in self.input_names]
        self.output_names = self.net.get_output_names(self.graph_name)
        self.output_shapes = [self.net.get_output_shape(self.graph_name, name) for name in self.output_names]
        logging.debug(str(("graph_name: {}, input_names & input_shapes: ".format(self.graph_name), self.input_names, self.input_shapes)))
        logging.debug(str(("graph_name: {}, output_names & output_shapes: ".format(self.graph_name), self.output_names, self.output_shapes)))

        self.input_name = self.input_names[0]
        self.output_name = self.output_names[0]
        self.input_dtype = self.net.get_input_dtype(self.graph_name, self.input_name)
        self.output_dtype = self.net.get_output_dtype(self.graph_name, self.output_name)
        # define input and ouput shape
        self.input_shape = self.net.get_input_shape(self.graph_name, self.input_name)
        self.output_shape = self.net.get_output_shape(self.graph_name, self.output_name)
        # init bmcv for preprocess
        self.handle = self.net.get_handle()
        self.bmcv = sail.Bmcv(self.handle)
        self.img_dtype = self.bmcv.get_bm_image_data_format(self.input_dtype)
        print(self.img_dtype)

        self.input_scale = self.net.get_input_scale(self.graph_name, self.input_name)
        self.output_scale = self.net.get_output_scale(self.graph_name, self.output_name)

        self.mean=[0.485, 0.456, 0.406]
        self.std=[0.229, 0.224, 0.225]

        self.a = [1/(255.*x) for x in self.std]
        self.b = [-x/y for x,y in zip(self.mean, self.std)]

        self.ab = []
        for i in range(3):
            self.ab.append(self.a[i]*self.input_scale)
            self.ab.append(self.b[i]*self.input_scale)

        self.batch_size = self.input_shape[0]
        self.net_h = self.input_shape[2]
        self.net_w = self.input_shape[3]
        
        self.dt = 0.0

        self.output_tensor = sail.Tensor(self.handle, self.output_shape, self.output_dtype,  True, True)
        self.output_tensors = {self.output_name: self.output_tensor}

    def preprocess_bmcv(self, input_bmimg, output_bmimg):
        if input_bmimg.format()==sail.Format.FORMAT_YUV420P:
            input_bmimg_bgr = self.bmcv.yuv2bgr(input_bmimg)
        else:
            input_bmimg_bgr = input_bmimg

        resize_bmimg = self.bmcv.resize(input_bmimg_bgr, self.net_w, self.net_h)
        resize_bmimg_rgb = sail.BMImage(self.handle, self.net_h, self.net_w, \
                        sail.Format.FORMAT_RGB_PLANAR, resize_bmimg.dtype())
        self.bmcv.convert_format(resize_bmimg, resize_bmimg_rgb)
        self.bmcv.convert_to(resize_bmimg_rgb, output_bmimg, ((self.ab[0], self.ab[1]), \
                                       (self.ab[2], self.ab[3]), \
                                       (self.ab[4], self.ab[5])))
        return output_bmimg

    def predict(self, input_tensor):
        input_tensors = {self.input_name: input_tensor}

        t0 = time.time()
        self.net.process(self.graph_name, input_tensors, self.output_tensors)
        self.dt += time.time() - t0

        outputs = self.output_tensor.asnumpy() * self.output_scale
        return outputs

    def postprocess(self, outputs):
        res = list()
        outputs_exp = np.exp(outputs)
        outputs = outputs_exp / np.sum(outputs_exp, axis=1)[:,None]
        predictions = np.argmax(outputs, axis = 1)
        for pred, output in zip(predictions, outputs):
            score = output[pred]
            res.append((pred,score))
        return res

    def __call__(self, bmimg_list):
        img_num = len(bmimg_list)
        assert img_num <= self.batch_size

        if self.batch_size == 1:
            for bmimg in bmimg_list:            
                output_bmimg = sail.BMImage(self.handle, self.net_h, self.net_w, \
                        sail.Format.FORMAT_RGB_PLANAR, self.img_dtype)
                output_bmimg = self.preprocess_bmcv(bmimg, output_bmimg)
                input_tensor = sail.Tensor(self.handle, self.input_shape,  self.input_dtype,  False, False)
                self.bmcv.bm_image_to_tensor(output_bmimg, input_tensor)
                outputs = self.predict(input_tensor)
                
        else:
            BMImageArray = eval('sail.BMImageArray{}D'.format(self.batch_size))
            bmimgs = BMImageArray()
            for i in range(img_num):
                output_bmimg = sail.BMImage(self.handle, self.net_h, self.net_w, \
                    sail.Format.FORMAT_RGB_PLANAR, self.img_dtype)
                output_bmimg = self.preprocess_bmcv(bmimg_list[i], output_bmimg)
                # self.preprocess_bmcv(bmimg_list[i], output_bmimg)
                bmimgs[i] = output_bmimg.data()
            input_tensor = sail.Tensor(self.handle, self.input_shape,  self.input_dtype,  False, False)
            self.bmcv.bm_image_to_tensor(bmimgs, input_tensor)
            outputs = self.predict(input_tensor)[:img_num]

        res = self.postprocess(outputs)

        return res

    def get_time(self):
        return self.dt

def main(args):
    resnet = Resnet(args)
    batch_size = resnet.batch_size

    output_dir = "./results"
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    
    if not os.path.isdir(args.input_path):
        raise Exception('{} is not a directory.'.format(args.input_path))

    bmimg_list = []
    filename_list = []
    res_dict = {}
    t1 = time.time()
    for filename in glob.glob(args.input_path+'/*'):
        if os.path.splitext(filename)[-1] not in ['.jpg','.png','.jpeg','.bmp','.JPEG','.JPG','.BMP']:
            continue
        decoder = sail.Decoder(filename, True, args.tpu_id)
        bmimg = sail.BMImage()
        ret = decoder.read(resnet.handle, bmimg)    
        if ret != 0:
            logging.error("{} decode failure.".format(filename))
            continue
        bmimg_list.append(bmimg)
        filename_list.append(filename)
        if len(bmimg_list) == batch_size:
            res_list = resnet(bmimg_list)
            for i, filename in enumerate(filename_list):
                logging.info("filename: {}, res: {}".format(filename, res_list[i]))
                res_dict[filename] = res_list[i]
            bmimg_list = []
            filename_list = []

    if len(bmimg_list):
        res_list = resnet(bmimg_list)
        for i, filename in enumerate(filename_list):
            logging.info("filename: {}, res: {}".format(filename, res_list[i]))
            res_dict[filename] = res_list[i]

    t2 = time.time()

    # save result
    result_file = os.path.split(args.bmodel)[-1] + "_" + os.path.split(args.input_path)[-1] + "_bmcv" + "_python_result.txt"
    fout = open(os.path.join(output_dir, result_file), 'w')
    for filename, (prediction, score) in res_dict.items():
        fout.write('\t'.join([filename, str(prediction), str(score)])+'\n')
    fout.close()
    logging.info("result saved in {}".format(os.path.join(output_dir, result_file)))
        
    # calculate speed   
    cn = len(res_dict)    
    logging.info("------------------ Inference Time Info ----------------------")
    inference_time = resnet.get_time() / cn
    logging.info("inference_time(ms): {:.2f}".format(inference_time * 1000))
    total_time = t2 - t1
    logging.info("total_time(ms): {:.2f}, img_num: {}".format(total_time * 1000, cn))
    average_latency = total_time / cn
    qps = 1 / average_latency
    logging.info("average latency time(ms): {:.2f}, QPS: {:2f}".format(average_latency * 1000, qps))

def argsparser():
    parser = argparse.ArgumentParser(prog=__file__)
    parser.add_argument('--input_path', type=str, default='../data/images/imagenet_val_1k/img', help='path of input, must be image directory')
    parser.add_argument('--bmodel', type=str, default='../data/models/BM1684X/resnet_fp32_b1.bmodel', help='path of bmodel')
    parser.add_argument('--tpu_id', type=int, default=0, help='tpu id')
    args = parser.parse_args()
    return args

if __name__ == '__main__':
    args = argsparser()
    main(args)
