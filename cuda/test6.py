#!/usr/bin/env python
# -*- coding: utf-8 -*-
 
from __future__ import division, print_function
 
"""
Multiples two square matrices together using multiple blocks and shared memory.
Each thread block is assigned a "tile" of the resulting matrix and is responsible
for generating the elements in that tile.  Each thread in a block computes one element
of the tile.
"""
 
import time
 
import numpy as np
# from numpy import linalg as la
 
import pycuda.driver as drv
import pycuda.compiler as compiler
import pycuda.gpuarray as gpuarray
 
# -- initialize the device
import pycuda.autoinit
 
# import skcuda.linalg as linalg
# linalg.init()
 
kernel_code = u"""
//__global__ void MatrixMulKernel(double *A, double *B, double *C,
__global__ void MatrixMulKernel(float *A, float *B, float *C,
    uint *params)
{
  const uint hA = params[0];
  const uint wA = params[1];
  const uint wB = params[2];

  const uint bs = 16;

  // Block index
  const uint bx = blockIdx.x;
  const uint by = blockIdx.y;

  // Thread index
  const uint tx = threadIdx.x;
  const uint ty = threadIdx.y;

  const uint aRow = bs * bx + ty;
  const uint bCol = bs * by + tx;

  const uint idx = bs*ty+tx;

  // The element of the block sub-matrix that is computed
  // by the thread
  float Csub = 0;

  // Loop over all the sub-matrices of A and B required to
  // compute the block sub-matrix
  for (uint a = 0; a < wA; a += bs)
    {

      // Shared memory for the sub-matrix of A
      __shared__ float As[bs*bs];
      // Shared memory for the sub-matrix of B
      __shared__ float Bs[bs*bs];

      uint idxA = a + tx;
      uint idxB = a + ty;

      if (aRow<hA && idxA < wA)
          As[idx] = A[aRow*wA+idxA];
      else
          As[idx] = 0;

      if (bCol<wB && idxB < wA)
          Bs[idx] = B[idxB*wB+bCol];
      else
          Bs[idx] = 0;

      // Synchronize to make sure the matrices are loaded
      __syncthreads();

      // Multiply the two matrices together;
      // each thread computes one element
      // of the block sub-matrix
#pragma unroll
      for (int k = 0; k < bs; ++k)
          Csub += As[ty*bs+k] * Bs[k*bs+tx];

      // Synchronize to make sure that the preceding
      // computation is done before loading two new
      // sub-matrices of A and B in the next iteration
      __syncthreads();
    }

  // Write the block sub-matrix to global memory;
  // each thread writes one element
  if (aRow<hA && bCol<wB) {
     C[aRow*wB+bCol] = Csub;
  }
}
"""

kernel_code = u"""
    __global__ void MatrixMulKernel(float *A, float *B, float *C, uint *params)
    {

    }
"""
 
# compile the kernel code
mod = compiler.SourceModule(kernel_code)
 
# get the kernel function from the compiled module
matrixmul = mod.get_function("MatrixMulKernel")
 
elapsed = 0
 
def dot_cuda(a,b, tt=np.float32):
    # define the matrix size
    MATRIX_ROW_SIZE,MATRIX_MID_SIZE = a.shape
    MATRIX_MID2_SIZE,MATRIX_COL_SIZE = b.shape
    if MATRIX_MID_SIZE!=MATRIX_MID2_SIZE:
        raise ValueError('Column num of A is not equal to row num of B.')
 
    # define size of blocks and tiles sub-matrix
    TILE_SIZE = 16
 
    a_cpu = a.astype(tt)
    b_cpu = b.astype(tt)
 
    start = drv.Event()
    stop = drv.Event()
 
    # transfer host (CPU) memory to device (GPU) memory
    a_gpu = gpuarray.to_gpu(a_cpu)
    b_gpu = gpuarray.to_gpu(b_cpu)
 
    # create empty gpu array for the result (C = A * B)
    c_gpu = gpuarray.empty((MATRIX_ROW_SIZE, MATRIX_COL_SIZE), tt)
 
    p = np.array([MATRIX_ROW_SIZE, MATRIX_MID_SIZE, MATRIX_COL_SIZE], dtype=np.uint32)
    p_gpu = gpuarray.to_gpu(p)
 
    start.record()
    # call the kernel on the card
    matrixmul(
        # inputs
        a_gpu, b_gpu,
        # output
        c_gpu,
        # shape,
        p_gpu,
        # grid of multiple blocks
        grid = ((MATRIX_ROW_SIZE-1) // TILE_SIZE+1, (MATRIX_COL_SIZE-1) // TILE_SIZE+1),
        # block of multiple threads
        block = (TILE_SIZE, TILE_SIZE, 1),
        )
    stop.record()
    c_cpu = c_gpu.get()
    stop.synchronize()
    global elapsed
    elapsed = stop.time_since(start)
    return c_cpu
 
# def dot_cuda2(a,b,tt=np.float32):
#     a_cpu = a.astype(tt)
#     b_cpu = b.astype(tt)
#
#     start = drv.Event()
#     stop = drv.Event()
#
#     start.record()
#
#     # transfer host (CPU) memory to device (GPU) memory
#     a_gpu = gpuarray.to_gpu(a_cpu)
#     b_gpu = gpuarray.to_gpu(b_cpu)
#
#     c_gpu = linalg.dot(a_gpu,b_gpu)
#     c_cpu = c_gpu.get()
#     stop.record()
#     stop.synchronize()
#     global elapsed
#     elapsed = stop.time_since(start)
#     return c_cpu
 
if __name__ == '__main__':
    print('(   hA,wA/hB,   wB) np(GFlop/s) cublas(GFlop/s) pycuda(GFlop/s)')
    for s in xrange(10,400,20):
        MATRIX_ROW_SIZE = 16*10
        MATRIX_MID_SIZE = 16*100
        MATRIX_COL_SIZE = 16*s
        print('({:5d},{:5d},{:5d})'.format(MATRIX_ROW_SIZE,MATRIX_MID_SIZE,MATRIX_COL_SIZE),end='\t')
 
        flopsPerMatrixMul = 2.0 * MATRIX_ROW_SIZE * MATRIX_MID_SIZE * MATRIX_COL_SIZE
 
        # create two random square matrices
        a_cpu = np.random.randn(MATRIX_ROW_SIZE, MATRIX_MID_SIZE)
        b_cpu = np.random.randn(MATRIX_MID_SIZE, MATRIX_COL_SIZE)
 
        # compute reference on the CPU to verify GPU computation
        t0=time.clock()
        c_cpu = np.dot(a_cpu, b_cpu)
        t1=time.clock()
        elapsed = t1-t0
        gigaFlops = (flopsPerMatrixMul * 1.0e-9) / elapsed
        print(' numpy={:.2f}'.format(gigaFlops), end='\t')
 
        # c_gpu2 = dot_cuda2(a_cpu,b_cpu, np.float32)
        # gigaFlops = (flopsPerMatrixMul * 1.0e-9) / (elapsed / 1000.0)
        # print('cublas={:.2f}'.format(gigaFlops), end='\t')
 
        c_gpu = dot_cuda(a_cpu,b_cpu, np.float32)
        gigaFlops = (flopsPerMatrixMul * 1.0e-9) / (elapsed / 1000.0)
        print('pycuda={:.2f}'.format(gigaFlops), end='\t')
 
        print()
 
        # if not np.allclose(c_gpu, c_gpu2, atol=1e-3):
        #     print('gpu-gpu results are not same.')
        if not np.allclose(c_cpu, c_gpu, atol=1e-3):
            print('cpu-gpu results are not same.',)
