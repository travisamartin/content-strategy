```mermaid
graph TD;
  NGINX["NGINX Documentation"]
  
  NGINX -->|F5| NGINXOne["NGINX One Console"]
  NGINXOne --> About
  NGINXOne --> "Get Started"
  NGINXOne --> "How-to Guides"
  NGINXOne --> API
  NGINXOne --> Glossary
  NGINXOne --> Changelog

  NGINX -->|F5| NGINXPlus["NGINX Plus"]
  NGINXPlus --> "Admin Guide"
  NGINXPlus --> "Deployment Guides"
  NGINXPlus --> Releases
  NGINXPlus --> "Technical Specifications"
  NGINXPlus --> "Open Source Components"
  NGINXPlus --> "NGINX Plus FIPS Compliance"
  NGINXPlus --> "NGINX Directives Index"

  NGINX -->|F5| InstanceMgr["NGINX Instance Manager"]
  InstanceMgr --> Fundamentals
  InstanceMgr --> Deploy
  InstanceMgr --> "Disconnected Environments"
  InstanceMgr --> "Platform Administration"
  InstanceMgr --> "System Configuration"
  InstanceMgr --> Monitoring
  InstanceMgr --> "NGINX Configs"
  InstanceMgr --> "NGINX Instances"
  InstanceMgr --> Support
  InstanceMgr --> Releases

  NGINX -->|F5| IngressCtrl["NGINX Ingress Controller"]
  IngressCtrl --> Overview
  IngressCtrl --> "Technical Specifications"
  IngressCtrl --> Installation
  IngressCtrl --> Configuration
  IngressCtrl --> "Logging & Monitoring"
  IngressCtrl --> Troubleshooting
  IngressCtrl --> Tutorials
  IngressCtrl --> Releases
  IngressCtrl --> Community

  NGINX -->|F5| GatewayFabric["NGINX Gateway Fabric"]
  GatewayFabric --> Overview
  GatewayFabric --> "Get Started"
  GatewayFabric --> Installation
  GatewayFabric --> "How-to Guides"
  GatewayFabric --> Reference
  GatewayFabric --> Support
  GatewayFabric --> Releases

  NGINX -->|F5| Agent["NGINX Agent"]
  Agent --> Overview
  Agent --> "Technical Specifications"
  Agent --> "Installation & Upgrade"
  Agent --> Configuration
  Agent --> Contribute
  Agent --> Changelog

  NGINX -->|F5| AppProtectWAF["F5 NGINX App Protect WAF"]
  AppProtectWAF --> "Version 4 & Earlier"
  AppProtectWAF --> "Version 5"

  NGINX -->|F5| AppProtectDoS["F5 NGINX App Protect DoS"]
  AppProtectDoS --> Deployment
  AppProtectDoS --> "Directives & Policy"
  AppProtectDoS --> Monitoring
  AppProtectDoS --> Troubleshooting
  AppProtectDoS --> Releases

  NGINX -->|Azure| NGINXAAS["NGINX as a Service for Azure"]
  NGINXAAS --> Overview
  NGINXAAS --> "Getting Started"
  NGINXAAS --> "NGINX App Protect WAF (Preview)"
  NGINXAAS --> "Logging & Monitoring"
  NGINXAAS --> "Marketplace Billing"
  NGINXAAS --> "Client Tools"
  NGINXAAS --> "Quickstart Guides"
  NGINXAAS --> Troubleshooting
  NGINXAAS --> FAQ
  NGINXAAS --> Changelog
  NGINXAAS --> "Known Issues"
  ```