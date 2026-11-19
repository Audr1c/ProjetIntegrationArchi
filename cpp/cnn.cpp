#include "utils.hpp"
#include <vector>



template <
    int W_i, int I_i, bool S_i,    //Input image

    int W_k1, int I_k1, bool S_k1, //Kernel for 1st conv
    int W_b1, int I_b1, bool S_b1, //Bias for 1st conv

    int W_k2, int I_k2, bool S_k2, //Kernel for 2nd conv
    int W_b2, int I_b2, bool S_b2, //Bias for 2nd conv

    int W_k3, int I_k3, bool S_k3, //Kernel for 3rd conv
    int W_b3, int I_b3, bool S_b3, //Bias for 3rd conv

    int W_pk, int I_pk, bool S_pk, //Perceptron matrix
    int W_pb, int I_pb, bool S_pb, //Perceptron bias

    int W_o, int I_o, bool S_o     //Output image
>
vector<ac_fixed<W_o, I_o, S_o>> cnn(
    imageT  <W_i, I_i, S_i>     image1, 
    kernelT <W_k1, I_k1, S_k1>& ker1,
    kernelT <W_k2, I_k2, S_k2>& ker2,
    kernelT <W_k3, I_k3, S_k3>& ker3,
    biasT   <W_b1, I_b1, S_b1>& bia1,
    biasT   <W_b1, I_b1, S_b1>& bia2,
    biasT   <W_b1, I_b1, S_b1>& bia3,
    vector<ac_fixed<W_pk, I_pk, S_pk>> & per_k, //perceptron kernel
    vector<ac_fixed<W_pb, I_pb, S_pb>> & per_b  //perceptron bias
) {


    //=== 1ST CONV ===//
    imageT<16, 8, true> image2;
    image2 = convolution_feature<16, 8, true>(
        image1,
        ker1, 
        bia1
    );

    relu(image2);

    //=== 1ST MAX POOL ===//
    imageT<16, 8, true> image3;
    image3 = max_pool<16, 8, true>(image2);



    //=== 2ND CONV ===//
    imageT<16, 8, true> image4;
    image4 = convolution_feature<16, 8, true>(
        image3,
        ker2, 
        bia2
    );

   
    relu(image4);

    //=== 2ND MAX POOL ===//
    imageT<16, 8, true> image5;
    image5 = max_pool<16, 8, true>(image4);



    //=== 3RD CONV ===//
    imageT<16, 8, true> image6;
    image6 = convolution_feature<16, 8, true>(
        image5,
        ker3, 
        bia3
    );

    relu(image6);

    //=== 3RD MAX POOL ===//
    imageT<16, 8, true> image7;
    image7 = max_pool<16, 8, true>(image6);



    //=== PERCEPTRON ===//
    vector<ac_fixed<W_o, I_o, S_o>> output;
    output = m_acc<W_o, I_o, S_o>(image7, per_k, per_b);


    return output;


}





