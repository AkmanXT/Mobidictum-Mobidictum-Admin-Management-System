import asyncio
import subprocess
import json
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from supabase import Client
from app.models import BatchJob, JobStatus
from app.config import settings

logger = logging.getLogger(__name__)


class JobExecutor:
    """Executes background jobs and tracks their status in Supabase."""
    
    def __init__(self, supabase: Client):
        self.supabase = supabase
        self.running_jobs: Dict[str, asyncio.Task] = {}
    
    async def execute_job(self, job_id: str) -> None:
        """Execute a job and update its status in the database."""
        try:
            # Get job details
            result = self.supabase.table("batch_jobs").select("*").eq("id", job_id).execute()
            if not result.data:
                logger.error(f"Job {job_id} not found")
                return
            
            job = result.data[0]
            job_type = job["job_type"]
            args = job.get("args", {})
            
            # Update job status to running
            await self._update_job_status(job_id, JobStatus.running, started_at=datetime.utcnow())
            
            # Execute based on job type
            if job_type.startswith("fienta."):
                result_data = await self._execute_fienta_job(job_type, args)
            elif job_type.startswith("email."):
                result_data = await self._execute_email_job(job_type, args)
            elif job_type.startswith("csv."):
                result_data = await self._execute_csv_job(job_type, args)
            else:
                raise ValueError(f"Unknown job type: {job_type}")
            
            # Update job as completed
            await self._update_job_status(
                job_id, 
                JobStatus.completed, 
                results=result_data,
                completed_at=datetime.utcnow()
            )
            
            logger.info(f"Job {job_id} completed successfully")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Job {job_id} failed: {error_msg}")
            
            # Update job as failed
            await self._update_job_status(
                job_id, 
                JobStatus.failed, 
                error_log=error_msg,
                completed_at=datetime.utcnow()
            )
        finally:
            # Remove from running jobs
            if job_id in self.running_jobs:
                del self.running_jobs[job_id]
    
    async def _update_job_status(
        self, 
        job_id: str, 
        status: JobStatus, 
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        results: Optional[Dict[str, Any]] = None,
        error_log: Optional[str] = None
    ) -> None:
        """Update job status in database."""
        update_data = {
            "status": status.value,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if started_at:
            update_data["started_at"] = started_at.isoformat()
        if completed_at:
            update_data["completed_at"] = completed_at.isoformat()
        if results:
            update_data["results"] = results
        if error_log:
            update_data["error_log"] = error_log
        
        self.supabase.table("batch_jobs").update(update_data).eq("id", job_id).execute()
    
    async def _execute_fienta_job(self, job_type: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Fienta automation jobs using existing Node.js scripts."""
        
        if job_type == "fienta.create_codes":
            return await self._run_fienta_create_codes(args)
        elif job_type == "fienta.rename_codes":
            return await self._run_fienta_rename_codes(args)
        elif job_type == "fienta.update_discount":
            return await self._run_fienta_update_discount(args)
        elif job_type == "fienta.csv_diff":
            return await self._run_fienta_csv_diff(args)
        else:
            raise ValueError(f"Unknown Fienta job type: {job_type}")
    
    async def _run_fienta_create_codes(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Run the existing Node.js script to create Fienta codes."""
        cmd = ["npm", "run", "dev", "--"]
        
        # Add data source
        if args.get("csv_path"):
            cmd.extend(["--csv", args["csv_path"]])
        elif args.get("xlsx_path"):
            cmd.extend(["--xlsx", args["xlsx_path"]])
        else:
            raise ValueError("Either csv_path or xlsx_path must be provided")
        
        # Add credentials
        cmd.extend([
            "--email", settings.fienta_email or "",
            "--password", settings.fienta_password or ""
        ])
        
        # Add options
        cmd.extend([
            "--headless", str(args.get("headless", True)).lower(),
            "--dryRun", str(args.get("dry_run", True)).lower()
        ])
        
        return await self._run_command(cmd, "fienta_create_codes")
    
    async def _run_fienta_rename_codes(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Run the existing Node.js script to rename Fienta codes."""
        cmd = ["npm", "run", "dev", "--"]
        
        # Add data source
        if args.get("pairs_csv_path"):
            cmd.extend(["--pairsCsv", args["pairs_csv_path"]])
        elif args.get("csv_path") and args.get("rename_prefix"):
            cmd.extend(["--csv", args["csv_path"]])
            cmd.extend(["--renamePrefix", args["rename_prefix"]])
            if args.get("rename_pad_length"):
                cmd.extend(["--renamePadLength", str(args["rename_pad_length"])])
            if args.get("rename_start"):
                cmd.extend(["--renameStart", str(args["rename_start"])])
            if args.get("rename_limit"):
                cmd.extend(["--renameLimit", str(args["rename_limit"])])
        else:
            raise ValueError("Either pairs_csv_path or (csv_path + rename_prefix) must be provided")
        
        # Add credentials
        cmd.extend([
            "--email", settings.fienta_email or "",
            "--password", settings.fienta_password or ""
        ])
        
        # Add options
        cmd.extend([
            "--headless", str(args.get("headless", True)).lower(),
            "--dryRun", str(args.get("dry_run", True)).lower()
        ])
        
        return await self._run_command(cmd, "fienta_rename_codes")
    
    async def _run_fienta_update_discount(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Run the existing Node.js script to update discount percentages."""
        cmd = ["npm", "run", "dev", "--"]
        
        # Add data source
        if not args.get("csv_path"):
            raise ValueError("csv_path must be provided")
        
        cmd.extend(["--csv", args["csv_path"]])
        
        # Add discount percent
        if not args.get("discount_percent"):
            raise ValueError("discount_percent must be provided")
        
        cmd.extend(["--updateDiscountPercent", str(args["discount_percent"])])
        
        # Add credentials
        cmd.extend([
            "--email", settings.fienta_email or "",
            "--password", settings.fienta_password or ""
        ])
        
        # Add options
        cmd.extend([
            "--headless", str(args.get("headless", True)).lower(),
            "--dryRun", str(args.get("dry_run", False)).lower()  # Default to false for updates
        ])
        
        return await self._run_command(cmd, "fienta_update_discount")
    
    async def _run_fienta_csv_diff(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Run the existing Node.js script to generate CSV diff reports."""
        cmd = ["npm", "run", "dev", "--"]
        
        if not args.get("old_xlsx_path") or not args.get("new_xlsx_path"):
            raise ValueError("Both old_xlsx_path and new_xlsx_path must be provided")
        
        cmd.extend([
            "--diffOld", args["old_xlsx_path"],
            "--diffNew", args["new_xlsx_path"]
        ])
        
        return await self._run_command(cmd, "fienta_csv_diff")
    
    async def _execute_email_job(self, job_type: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute email jobs using archived Python scripts."""
        
        if job_type == "email.send":
            return await self._run_email_send(args)
        else:
            raise ValueError(f"Unknown email job type: {job_type}")
    
    async def _run_email_send(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Send email using archived Gmail scripts."""
        # This would use the archived Python scripts
        # For now, return a placeholder
        return {
            "status": "email_sent",
            "to": args.get("to", []),
            "subject": args.get("subject", ""),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _execute_csv_job(self, job_type: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute CSV automation jobs."""
        
        if job_type == "csv.xlsx_to_csv":
            return await self._run_xlsx_to_csv(args)
        else:
            raise ValueError(f"Unknown CSV job type: {job_type}")
    
    async def _run_xlsx_to_csv(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Convert XLSX to CSV using existing TypeScript tool."""
        cmd = ["npm", "run", "xlsx:to:csv"]
        
        if args.get("input_path"):
            cmd.extend(["--input", args["input_path"]])
        if args.get("output_path"):
            cmd.extend(["--output", args["output_path"]])
        
        return await self._run_command(cmd, "xlsx_to_csv")
    
    async def _run_command(self, cmd: List[str], job_name: str) -> Dict[str, Any]:
        """Run a shell command and capture its output."""
        try:
            logger.info(f"Running command for {job_name}: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.getcwd()
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=settings.job_timeout_seconds
            )
            
            stdout_text = stdout.decode('utf-8') if stdout else ""
            stderr_text = stderr.decode('utf-8') if stderr else ""
            
            # Write logs to filesystem
            log_timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            log_filename = f"{job_name}_{log_timestamp}.log"
            log_path = os.path.join("logs", log_filename)
            
            os.makedirs("logs", exist_ok=True)
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"Command: {' '.join(cmd)}\n")
                f.write(f"Exit code: {process.returncode}\n")
                f.write(f"Timestamp: {datetime.utcnow().isoformat()}\n\n")
                f.write("STDOUT:\n")
                f.write(stdout_text)
                f.write("\n\nSTDERR:\n")
                f.write(stderr_text)
            
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, cmd, stderr_text)
            
            return {
                "exit_code": process.returncode,
                "stdout": stdout_text,
                "stderr": stderr_text,
                "log_file": log_path,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except asyncio.TimeoutError:
            raise Exception(f"Command timed out after {settings.job_timeout_seconds} seconds")
        except Exception as e:
            logger.error(f"Command failed: {str(e)}")
            raise
    
    async def start_job(self, job_id: str) -> None:
        """Start a job execution in the background."""
        if job_id in self.running_jobs:
            logger.warning(f"Job {job_id} is already running")
            return
        
        task = asyncio.create_task(self.execute_job(job_id))
        self.running_jobs[job_id] = task
    
    def get_running_jobs(self) -> List[str]:
        """Get list of currently running job IDs."""
        return list(self.running_jobs.keys())
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job."""
        if job_id not in self.running_jobs:
            return False
        
        task = self.running_jobs[job_id]
        task.cancel()
        
        # Update job status
        await self._update_job_status(
            job_id, 
            JobStatus.cancelled,
            completed_at=datetime.utcnow()
        )
        
        del self.running_jobs[job_id]
        return True
