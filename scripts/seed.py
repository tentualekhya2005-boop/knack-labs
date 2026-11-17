import os
import psycopg2

db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:@127.0.0.1:5432/linkops")

def seed():
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        for i in range(1, 26):
            cur.execute(
                "INSERT INTO links (code, long_url, created_by, created_at) VALUES (%s, %s, %s, NOW()) ON CONFLICT (code) DO NOTHING",
                (f"test{i:02d}", f"https://example.com/{i}", "default")
            )
        conn.commit()
    conn.close()
    print("seeded 25 links")

if __name__ == "__main__":
    seed()
