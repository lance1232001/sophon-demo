# -*- coding: utf-8 -*- 
import os
import time
import cv2
import numpy as np
import argparse
import json
import sophon.sail as sail
import logging
logging.basicConfig(level=logging.DEBUG)

CHARS = ['京', '沪', '津', '渝', '冀', '晋', '蒙', '辽', '吉', '黑',
         '苏', '浙', '皖', '闽', '赣', '鲁', '豫', '鄂', '湘', '粤',
         '桂', '琼', '川', '贵', '云', '藏', '陕', '甘', '青', '宁',
         '新',
         '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
         'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K',
         'L', 'M', 'N', 'P', 'Q', 'R', 'S', 'T', 'U', 'V',
         'W', 'X', 'Y', 'Z', 'I', 'O', '-'
         ]

CHARS_DICT = {i:char for i, char in enumerate(CHARS)}

class LPRNet(object):
    def __init__(self, args):
        # load bmodel
        self.net = sail.Engine(args.bmodel, args.tpu_id, sail.IOMode.SYSIO)
        self.graph_name = self.net.get_graph_names()[0]
        self.input_name = self.net.get_input_names(self.graph_name)[0]
        self.input_shape = self.net.get_input_shape(self.graph_name, self.input_name)
        logging.debug("load {} success!".format(args.bmodel))

        self.batch_size = self.input_shape[0]
        self.net_h = self.input_shape[2]
        self.net_w = self.input_shape[3]
        
        self.dt = 0.0

    def preprocess(self, img):
        h, w, _ = img.shape
        if h != self.net_h or w != self.net_w:
            img = cv2.resize(img, (self.net_w, self.net_h))
        img = img.astype('float32')
        img -= 127.5
        img *= 0.0078125
        img = np.transpose(img, (2, 0, 1))
        return img

    def predict(self, input_img):
        input_data = {self.input_name: input_img}
        t0 = time.time()
        outputs = self.net.process(self.graph_name, input_data)
        self.dt += time.time() - t0
        return list(outputs.values())[0]

    def postprocess(self, outputs):
        res = list()
        outputs = np.argmax(outputs, axis = 1)
        for output in outputs:
            no_repeat_blank_label = list()
            pre_c = output[0]
            if pre_c != len(CHARS) - 1:
                no_repeat_blank_label.append(CHARS_DICT[pre_c])
            for c in output:
                if (pre_c == c) or (c == len(CHARS) - 1):
                    if c == len(CHARS) - 1:
                        pre_c = c
                    continue
                no_repeat_blank_label.append(CHARS_DICT[c])
                pre_c = c
            res.append(''.join(no_repeat_blank_label)) 

        return res

    def __call__(self, img_list):
        img_num = len(img_list)
        img_input_list = []
        for img in img_list:
            img = self.preprocess(img)
            img_input_list.append(img)
        
        if img_num == self.batch_size:
            input_img = np.stack(img_input_list)
            outputs = self.predict(input_img)
        else:
            input_img = np.zeros(self.input_shape, dtype='float32')
            input_img[:img_num] = np.stack(img_input_list)
            outputs = self.predict(input_img)[:img_num]

        res = self.postprocess(outputs)

        return res

    def get_time(self):
        return self.dt

def main(args):
    lprnet = LPRNet(args)
    batch_size = lprnet.batch_size

    output_dir = "./results"
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    
    if not os.path.isdir(args.input_path):
        # logging.error("input_path must be an image directory.")
        # return 0
        raise Exception('{} is not a directory.'.format(args.input_path))
        

    img_list = []
    filename_list = []
    res_dict = {}
    t1 = time.time()
    for root, dirs, filenames in os.walk(args.input_path):
        filenames.sort(key=lambda x:x[1:-4])
        for filename in filenames:
            if os.path.splitext(filename)[-1] not in ['.jpg','.png','.jpeg','.bmp','.JPEG','.JPG','.BMP']:
                continue
            img_file = os.path.join(root, filename)
            src_img = cv2.imdecode(np.fromfile(img_file, dtype=np.uint8), -1)
            if src_img is None:
                logging.error("{} imdecode is None.".format(img_file))
                continue
            img_list.append(src_img)
            filename_list.append(filename)
            if len(img_list) == batch_size:
                res_list = lprnet(img_list)
                for i, filename in enumerate(filename_list):
                    logging.info("filename: {}, res: {}".format(filename, res_list[i]))
                    res_dict[filename] = res_list[i]
                img_list = []
                filename_list = []
    if len(img_list):
        res_list = lprnet(img_list)
        for i, filename in enumerate(filename_list):
            logging.info("filename: {}, res: {}".format(filename, res_list[i]))
            res_dict[filename] = res_list[i]

    t2 = time.time()

    # save result
    json_name = os.path.split(args.bmodel)[-1] + "_" + os.path.split(args.input_path)[-1] + "_opencv" + "_python_result.json"
    with open(os.path.join(output_dir, json_name), 'w') as jf:
        json.dump(res_dict, jf, indent=4, ensure_ascii=False)
    logging.info("result saved in {}".format(os.path.join(output_dir, json_name)))
	    
    # calculate speed  
    cn = len(res_dict)    
    logging.info("------------------ Inference Time Info ----------------------")
    inference_time = lprnet.get_time() / cn
    logging.info("inference_time(ms): {:.2f}".format(inference_time * 1000))
    total_time = t2 - t1
    logging.info("total_time(ms): {:.2f}, img_num: {}".format(total_time * 1000, cn))
    average_latency = total_time / cn
    qps = 1 / average_latency
    logging.info("average latency time(ms): {:.2f}, QPS: {:2f}".format(average_latency * 1000, qps))
        
def argsparser():
    parser = argparse.ArgumentParser(prog=__file__)
    parser.add_argument('--input_path', type=str, default='../data/images/test', help='path of input, must be image directory')
    parser.add_argument('--bmodel', type=str, default='../data/models/lprnet_fp32_1b4b.bmodel', help='path of bmodel')
    parser.add_argument('--tpu_id', type=int, default=0, help='tpu id')
    args = parser.parse_args()
    return args

if __name__ == '__main__':
    args = argsparser()
    main(args)
