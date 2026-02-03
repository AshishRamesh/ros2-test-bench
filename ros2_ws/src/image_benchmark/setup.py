from setuptools import setup

package_name = 'image_benchmark'

setup(
    name=package_name,
    version='1.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='User',
    maintainer_email='user@example.com',
    description='ROS 2 middleware benchmarking package for image streaming',
    license='MIT',
    entry_points={
        'console_scripts': [
            'benchmark_publisher = image_benchmark.benchmark_publisher:main',
            'benchmark_subscriber = image_benchmark.benchmark_subscriber:main',
            'compare_results = image_benchmark.compare_results:main',
        ],
    },
)
