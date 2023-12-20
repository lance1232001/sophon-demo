//===----------------------------------------------------------------------===//
//
// Copyright (C) 2022 Sophgo Technologies Inc.  All rights reserved.
//
// SOPHON-DEMO is licensed under the 2-Clause BSD License except for the
// third-party components.
//
//===----------------------------------------------------------------------===//

#ifndef PPYOLOE_H
#define PPYOLOE_H

#include <iostream>
#include <vector>
#include "opencv2/opencv.hpp"
#include "bmnn_utils.h"
#include "engine.h"
#include "utils.hpp"
#include "bm_wrapper.hpp"
#include "cvwrapper.h"

// Define USE_OPENCV for enabling OPENCV related funtions in bm_wrapper.hpp
#define USE_OPENCV 1
#define DEBUG 0

struct ppYoloeBox {
    int x, y, width, height;
    float score;
    int class_id;
};

using ppYoloeBoxVec = std::vector<ppYoloeBox>;

class ppYoloe {
    std::shared_ptr<sail::Engine>              engine;
    std::shared_ptr<sail::Bmcv>                bmcv;
    std::vector<std::string>                   graph_names;
    std::vector<std::string>                   input_names;
    std::vector<int>                           input_img_shape;
    std::vector<int>                           input_ratio_shape;
    std::vector<std::string>                   output_names;
    std::vector<int>                           output_score_shape;
    std::vector<int>                           output_coordinate_shape;
    bm_data_type_t                             input_img_dtype;
    bm_data_type_t                             output_score_dtype;
    bm_data_type_t                             input_ratio_dtype;
    bm_data_type_t                             output_coordinate_dtype;
    std::shared_ptr<sail::Tensor>              input_img_tensor;
    std::shared_ptr<sail::Tensor>              input_ratio_tensor;
    std::shared_ptr<sail::Tensor>              output_score_tensor;
    std::shared_ptr<sail::Tensor>              output_coordinate_tensor;
    std::map<std::string, sail::Tensor*>       input_tensors;
    std::map<std::string, sail::Tensor*>       output_tensors;

    // configuration
    float m_confThreshold = 0.5;
    float m_nmsThreshold = 0.5;

    std::vector<std::string> m_class_names;
    int m_class_num = 80;  // default is coco names
    int m_net_h, m_net_w;
    int max_batch;
    float norm[6];
    float ab[6];

    TimeStamp* m_ts;

   private:
    int pre_process(sail::BMImage& input);
    template <std::size_t N>
    int pre_process(std::vector<sail::BMImage>& input);
    int post_process(std::vector<sail::BMImage>& images, std::vector<ppYoloeBoxVec>& detected_boxes);
    // int argmax(float* data, int dsize);
    int argmax_interval(float *data, int class_num, int box_num);
    std::vector<float> get_img_ratio(int src_w, int src_h, int dst_w, int dst_h);
    // static float get_aspect_scaled_ratio(int src_w, int src_h, int dst_w, int dst_h, bool* alignWidth);
    void NMS(ppYoloeBoxVec& dets, float nmsConfidence);

   public:
    ppYoloe(int dev_id, std::string bmodel_file);
    virtual ~ppYoloe();
    int Init(float confThresh = 0.5, float nmsThresh = 0.5, const std::string& coco_names_file = "");
    void enableProfile(TimeStamp* ts);
    int batch_size();
    int Detect(std::vector<sail::BMImage>& images, std::vector<ppYoloeBoxVec>& boxes);
    void draw_bmcv(int classId,float conf,int left,int top,int right,int bottom,sail::BMImage& frame,bool put_text_flag = false);
};

#endif  //! PPYOLOE_H
