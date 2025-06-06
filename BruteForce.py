BASE_URL = "https://uat.moc.gov.kh/news/"

for i in range(1, 3001):
    with open(f"BruteForce.txt", "a") as f:
        f.write(f"{BASE_URL}{i}\n")