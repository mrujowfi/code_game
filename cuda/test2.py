#coding=utf-8
#https://documen.tician.de/pycuda/

import pycuda.autoinit
import pycuda.driver as drv
import numpy
from pycuda.compiler import SourceModule
mod = SourceModule(u"""
    __global__ void multiply_them(float *dest, float *a, float *b)
    {
        const int i = threadIdx.x;
        dest[i] = threadIdx.x*100 + threadIdx.y*10 + threadIdx.z*1;
    }
    """)
multiply_them = mod.get_function("multiply_them")
a = numpy.random.randn(4).astype(numpy.float32)
b = numpy.random.randn(4).astype(numpy.float32)
dest = numpy.zeros_like(a)

multiply_them( drv.Out(dest), drv.In(a), drv.In(b), block=(4,3,2), grid=(1,1))
print help(multiply_them)
print len(dest)
# print a
# print b
print dest
# print dest-a*b

'''


def multiply_them(dest2, a, b):
    for i in range(len(a)):
        dest2.append(a[i] * b[i])

if __name__ == '__main__':
    dest2 = []
    multiply_them(dest2, a, b)
    print len(dest2)
'''