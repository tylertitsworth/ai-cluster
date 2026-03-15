{{- define "openclaw-agent-instance.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "openclaw-agent-instance.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else if .Values.instance.name -}}
{{- .Values.instance.name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- include "openclaw-agent-instance.name" . -}}
{{- end -}}
{{- end -}}

{{- define "openclaw-agent-instance.providerSecretName" -}}
{{- if .Values.secretRefs.providerSecret -}}
{{- .Values.secretRefs.providerSecret | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-provider-secrets" (include "openclaw-agent-instance.fullname" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "openclaw-agent-instance.discordSecretName" -}}
{{- if .Values.secretRefs.discordSecret -}}
{{- .Values.secretRefs.discordSecret | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-discord-secrets" (include "openclaw-agent-instance.fullname" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "openclaw-agent-instance.gatewayTokenSecretName" -}}
{{- if .Values.secretRefs.gatewayTokenSecret -}}
{{- .Values.secretRefs.gatewayTokenSecret | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-gateway-token" (include "openclaw-agent-instance.fullname" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
