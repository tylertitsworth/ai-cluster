import asyncio

from kernel_client import KernelClient


async def main():
    # Example AI agent using the kernel client
    async with KernelClient("192.168.1.91:8888") as client:
        # Example 1: Basic computation
        code1 = """
        import numpy as np

        # Create sample data
        data = np.random.normal(0, 1, 1000)

        # Compute statistics
        mean = np.mean(data)
        std = np.std(data)

        print(f"Mean: {mean:.2f}")
        print(f"Standard deviation: {std:.2f}")
        """

        result1 = await client.execute_code(code1)
        print("Example 1 result:")
        print(result1.output)

        # Example 2: Data visualization with base64 encoding
        code2 = """
        import matplotlib.pyplot as plt
        import seaborn as sns
        import io
        import base64

        # Create a simple plot
        plt.figure(figsize=(8, 6))
        sns.histplot(data, bins=30)
        plt.title('Distribution of Random Data')

        # Save plot to bytes buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close()

        # Convert to base64 string
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        print("Base64 encoded image data:")
        print(img_str)
        """

        result2 = await client.execute_code(code2)
        print("\nExample 2 result:")

        # Save the base64 data to a file
        if result2.success:
            img_data = result2.output.split("Base64 encoded image data:\n")[1].strip()
            import base64

            with open("distribution.png", "wb") as f:
                f.write(base64.b64decode(img_data))
            print("Plot saved as distribution.png")
        else:
            print("Error:", result2.error)


if __name__ == "__main__":
    asyncio.run(main())
