PATH := node_modules/.bin:$(PATH)
STACK_NAME ?= "marblecutter-virtual"

deploy: packaged.yaml
	sam deploy \
		--template-file $< \
		--stack-name $(STACK_NAME) \
		--capabilities CAPABILITY_IAM \
		--parameter-overrides DomainName=$(DOMAIN_NAME)

packaged.yaml: .aws-sam/build/template.yaml
	sam package --s3-bucket $(S3_BUCKET) --output-template-file $@

.aws-sam/build/template.yaml: template.yaml requirements.txt virtual/*.py
	sam build --use-container

clean:
	rm -rf .aws-sam/ packaged.yaml

server:
	docker build --build-arg http_proxy=$(http_proxy) -t quay.io/mojodna/marblecutter-virtual .
