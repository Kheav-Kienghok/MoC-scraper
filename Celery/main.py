from Celery.tasks import scrape_and_save_paired_content
import os
import time

# urls = [
#     "https://www.mfaic.gov.kh/Posts/2025-06-23-News-Inaugural-Meeting-of-the-Commission-for-the-Preparation-of-Documents-for-Submission-to-the-Internati-10-50-08",
#     "https://www.mfaic.gov.kh/Posts/2025-06-22-News-Diplomatic-Note-of-the-Ministry-of-Foreign-Affairs-and-International-Cooperation-to-strongly-protest-22-03-28",
#     "https://www.mfaic.gov.kh/Posts/2025-06-19-News-Meeting-on-the--Progress-of-Project-Implementation-of-the-Mekong-Lancang-Cooperation--MLC--Special-F-17-59-45"
# ]

with open("mfaic_urls.txt", "r", encoding="UTF-8") as file:
    urls = [line.strip() for line in file if line.strip()]

output_dir = "output"
output_file = os.path.join(output_dir, "mofa_news.csv")

# Ensure output directory exists
os.makedirs(output_dir, exist_ok=True)

# Record start time
start_time = time.time()
start_timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

print("📡 Starting scraping task...")
print(f"🔗 Processing {len(urls)} URLs")
print(f"⏰ Start time: {start_timestamp}")

# Submit task
result = scrape_and_save_paired_content.apply_async(args=[urls], kwargs={"output_file": output_file})

print("✅ Task submitted to Celery worker. Waiting for result...")

try:
    # Wait for completion (timeout in seconds)
    task_result = result.get(timeout=300)
    
    # Record end time
    end_time = time.time()
    end_timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    total_time = end_time - start_time
    
    print("🎉 Task completed successfully!")
    print(f"⏰ End time: {end_timestamp}")
    print(f"⏱️ Total execution time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
    print(f"📝 Result: {task_result}")

    # Check file
    if os.path.exists(output_file):
        file_size = os.path.getsize(output_file)
        print(f"📄 CSV file created: {output_file}")
        print(f"📦 File size: {file_size} bytes")
    else:
        print("⚠️ Warning: CSV file was not found after task finished.")

except Exception as e:
    # Record end time even on failure
    end_time = time.time()
    end_timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    total_time = end_time - start_time
    
    print("❌ Task failed with an error.")
    print(f"⏰ End time: {end_timestamp}")
    print(f"⏱️ Total execution time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
    print(f"🔍 Error: {e}")
    print(f"📊 Task state: {result.state}")
    if hasattr(result, "traceback") and result.traceback:
        print(f"📜 Traceback:\n{result.traceback}")