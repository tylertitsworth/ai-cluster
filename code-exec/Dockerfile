FROM jupyter/base-notebook:python-3.10

USER root
# Install system dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends     build-essential     && rm -rf /var/lib/apt/lists/*

USER ${NB_UID}
# Install Jupyter Kernel Gateway and other dependencies
RUN pip install --no-cache-dir     jupyter_kernel_gateway==2.5.2     numpy     pandas     matplotlib     seaborn     scikit-learn

# Add security configurations
COPY kernel_security.py /opt/conda/lib/python3.10/site-packages/
ENV JUPYTER_KERNEL_GATEWAY_KERNEL_SECURITY_CLASS=kernel_security.KernelSecurity

EXPOSE 8888
CMD ["jupyter", "kernelgateway", "--KernelGatewayApp.ip=0.0.0.0", "--KernelGatewayApp.allow_origin=*", "--KernelGatewayApp.allow_credentials=true", "--KernelGatewayApp.allow_headers=*"]
