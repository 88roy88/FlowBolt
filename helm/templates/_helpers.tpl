{{/*
Expand the name of the chart.
*/}}
{{- define "ai-builder.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "ai-builder.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- define "ai-builder.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "ai-builder.labels" -}}
helm.sh/chart: {{ include "ai-builder.chart" . }}
app.kubernetes.io/name: {{ include "ai-builder.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "ai-builder.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ai-builder.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
The name of the Secret containing credentials.
Falls back to the chart-generated secret if no existing secret is specified.
*/}}
{{- define "ai-builder.secretName" -}}
{{- if .Values.secrets.existingSecretName -}}
{{ .Values.secrets.existingSecretName }}
{{- else -}}
{{ include "ai-builder.fullname" . }}-secrets
{{- end }}
{{- end }}

{{/*
PostgreSQL connection URL — uses the subchart service when enabled,
otherwise falls back to secrets.databaseUrl (SQLite or external PG).
*/}}
{{- define "ai-builder.databaseUrl" -}}
{{- if .Values.postgresql.enabled -}}
postgresql://{{ .Values.postgresql.auth.username }}:{{ .Values.postgresql.auth.password }}@{{ include "ai-builder.fullname" . }}-postgresql:5432/{{ .Values.postgresql.auth.database }}
{{- else -}}
{{ .Values.secrets.databaseUrl | default "sqlite:////app/data/ai_builder.db" }}
{{- end }}
{{- end }}

{{/*
pnpm store path — shared PVC mount when enabled, pod-local path otherwise.
*/}}
{{- define "ai-builder.pnpmStorePath" -}}
{{- if .Values.backend.pnpmStorePvc.enabled -}}
/pnpm-store
{{- else -}}
/var/lib/ai-builder/workspaces/.pnpm-store
{{- end }}
{{- end }}
