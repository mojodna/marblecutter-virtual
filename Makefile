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

deploy-apex: project.json deps/deps.tgz
	apex deploy -l debug -E environment.json

.PHONY: project.json
project.json: project.json.hbs node_modules/.bin/interp
	interp < $< > $@

deploy-up: up.json deps/deps.tgz
	up $(ENV)

# always build this in case the *environment* changes
.PHONY: up.json
up.json: up.json.hbs node_modules/.bin/interp
	interp < $< > $@

node_modules/.bin/interp:
	npm install interp

deps/deps.tgz: deps/Dockerfile deps/required.txt
	docker run --rm --entrypoint tar $$(docker build --build-arg http_proxy=$(http_proxy) -t marblecutter-virtual-deps -q -f $< .) zc -C /var/task . > $@

clean:
	rm -f deps/deps.tgz

server:
	docker build --build-arg http_proxy=$(http_proxy) -t quay.io/mojodna/marblecutter-virtual .
