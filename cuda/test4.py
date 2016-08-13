import pycuda.gpuarray as gpuarray
import pycuda.driver as cuda
import pycuda.autoinit
import numpy
a_gpu = gpuarray.to_gpu(numpy.random.randn(4, 4))
print "a_gpu ="
print a_gpu
a_doubled = (2*a_gpu).get()
print
print "a_doubled ="
print a_doubled
