package com.example.batchprocessing;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import org.springframework.batch.item.ItemProcessor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.DataClassRowMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.stream.Collectors;

@Component
public class ProductItemProcessor implements ItemProcessor<Product, Product> {

	private static final Logger log = LoggerFactory.getLogger(ProductItemProcessor.class);

	@Autowired
	private JdbcTemplate jdbcTemplate;

	private Map<Long, String> loyalityCache;

    @Override
	public Product process(final Product product) {
		if (loyalityCache == null) {
			loyalityCache = jdbcTemplate
				.query("SELECT * FROM loyality_data", new DataClassRowMapper<>(Loyality.class))
				.stream()
				.collect(Collectors.toMap(Loyality::productSku, Loyality::loyalityData));
		}

		String loyalityData = loyalityCache.get(product.productSku());
		Product transformed = loyalityData != null
			? new Product(product.productId(), product.productSku(), product.productName(), product.productAmount(), loyalityData)
			: product;

		log.info("Transforming ({}) into ({})", product, transformed);

		return transformed;
	}

}
