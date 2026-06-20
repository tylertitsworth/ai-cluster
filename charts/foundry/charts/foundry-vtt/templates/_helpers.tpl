{{/* vim: set filetype=mustache: */}}
{{/*
Expand the name of the chart.
*/}}
{{- define "foundry-vtt.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "foundry-vtt.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "foundry-vtt.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Common labels
*/}}
{{- define "foundry-vtt.labels" -}}
helm.sh/chart: {{ include "foundry-vtt.chart" . }}
{{ include "foundry-vtt.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/*
Selector labels
*/}}
{{- define "foundry-vtt.selectorLabels" -}}
app.kubernetes.io/name: {{ include "foundry-vtt.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Create the name of the service account to use
*/}}
{{- define "foundry-vtt.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
    {{ default (include "foundry-vtt.fullname" .) .Values.serviceAccount.name }}
{{- else -}}
    {{ default "default" .Values.serviceAccount.name }}
{{- end -}}
{{- end -}}

{{/*
Create annotations for AWS LoadBalancers
*/}}
{{- define "foundry-vtt.cloudProvider.aws.loadBalacer.annotations" -}}
{{- if and .Values.cloudProviders.aws.loadBalancer (eq .Values.service.serviceType "LoadBalancer") }}
service.beta.kubernetes.io/aws-load-balancer-type: {{ .Values.cloudProviders.aws.loadBalancer.type | quote }}
service.beta.kubernetes.io/aws-load-balancer-backend-protocol: {{ .Values.cloudProviders.aws.loadBalancer.backendProtocol | quote }}
service.beta.kubernetes.io/aws-load-balancer-cross-zone-load-balancing-enabled: {{ .Values.cloudProviders.aws.loadBalancer.crossZoneLB | quote }}
{{- if .Values.service.tls }}
service.beta.kubernetes.io/aws-load-balancer-ssl-cert: arn:aws:acm:{{ .Values.cloudProviders.aws.region }}:{{ .Values.cloudProviders.aws.accountId }}:certificate/{{ .Values.cloudProviders.aws.loadBalancer.sslCertId }}
service.beta.kubernetes.io/aws-load-balancer-ssl-ports: {{ .Values.cloudProviders.aws.loadBalancer.sslPort | quote }}
{{- end }}
{{- range $key, $val := .Values.cloudProviders.aws.loadBalancer.extraConfigs }}
service.beta.kubernetes.io/aws-load-balancer-{{ $key }}: {{ $val }}
{{- end }}
{{- end }}
{{- end -}}

{{/*
Create annotations for AWS Service Accounts
*/}}
{{- define "foundry-vtt.cloudProvider.aws.serviceAccount.annotations" -}}
{{- $accountId := .Values.cloudProviders.aws.accountId }}
{{- if .Values.cloudProviders.aws.serviceAccount.enabled }}
{{- range .Values.cloudProviders.aws.serviceAccount.roles }}
eks.amazonaws.com/role-arn: arn:aws:iam::{{ $accountId }}:role/{{ . }}
{{- end }}
{{- end }}
{{- end -}}