# Task 03: Authentication and Authorization

## Description
This task upgrades the previous REST API by implementing robust security measures, ensuring that user data is protected and operations are restricted based on user roles.

## Security Features Implemented
* **Password Hashing:** Integrated `bcrypt` to securely salt and hash user passwords before storing them in the SQLite database.
* **JWT Authentication:** Implemented JSON Web Tokens (JWT). Users authenticate via a `/login` endpoint to receive a time-limited token.
* **Protected Routes:** Created a custom `@token_required` decorator middleware to block unauthorized access to standard CRUD operations.
* **Role-Based Access Control (RBAC):** Added user roles (`user` vs `admin`). Only administrators have the authorization to perform destructive actions, such as `DELETE` requests.
