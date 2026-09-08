from app.auth.security import hash_password, verify_password


if __name__ == "__main__":
    sample_password = "Sample-Password-123!"
    wrong_password = "wrong-password"

    hash_one = hash_password(sample_password)
    hash_two = hash_password(sample_password)

    hash_generated = (
        isinstance(hash_one, str)
        and len(hash_one) > 0
        and hash_one != sample_password
    )

    correct_verification = verify_password(sample_password, hash_one)
    wrong_verification = not verify_password(wrong_password, hash_one)
    unique_hashes = hash_one != hash_two
    both_verify = (
        verify_password(sample_password, hash_one)
        and verify_password(sample_password, hash_two)
    )

    print("Hash generated:", "YES" if hash_generated else "NO")
    print(
        "Correct password verification:",
        "PASS" if correct_verification else "FAIL"
    )
    print(
        "Wrong password verification:",
        "PASS" if wrong_verification else "FAIL"
    )
    print("Unique hashes:", "PASS" if unique_hashes else "FAIL")
    print(
        "Both hashes verify original password:",
        "PASS" if both_verify else "FAIL"
    )
