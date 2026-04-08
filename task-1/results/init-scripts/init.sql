-- Create application database and schema
CREATE USER postgres WITH PASSWORD '123456' SUPERUSER;
CREATE DATABASE productsdb;

\connect productsdb;

CREATE TABLE IF NOT EXISTS products (
    product_id   INT PRIMARY KEY,
    product_sku  VARCHAR(20),
    product_name VARCHAR(100),
    product_amount INT,
    product_data VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS loyality_data (
    product_sku   VARCHAR(20) PRIMARY KEY,
    loyality_data VARCHAR(50)
);
