# Fault Injection

Run these scripts only against an environment you are authorized to disrupt.

```powershell
.\performance\chaos\stop-order-worker.ps1
.\performance\chaos\stop-order-worker.ps1 -Restore
.\performance\chaos\stop-product-instance.ps1 -Instance 1
.\performance\chaos\stop-product-instance.ps1 -Instance 1 -Restore
```

The scripts stop and start existing Compose services. They do not delete containers, volumes, or data.
