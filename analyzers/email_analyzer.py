"""
email_analyzer.py - analyzes email artifacts
supports: PST (Outlook), MBOX (Thunderbird/Mac Mail), EML files, OST
extracts: emails, contacts, attachments, headers

REFACTORED: Now uses error_handler, dependency_manager, and progress_manager
"""

import email
import mailbox
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import quopri
import base64

# Import centralized management modules
from core.error_handler import (
    EmailAnalysisError,
    DependencyError,
    FileSystemError,
    handle_filesystem_errors,
    safe_directory_scan,
    log_error_report,
    logger
)
from core.dependency_manager import is_available, check_feature
from core.progress_manager import ProgressTracker, MultiStepProgressTracker


# Check for PST parsing library using dependency manager
if is_available('pypff'):
    try:
        import pypff
        logger.info("✓ pypff library available - PST/OST support enabled")
    except ImportError as e:
        logger.warning(f"pypff import failed despite being marked available: {e}")
else:
    logger.info("✗ pypff not available - PST/OST support disabled")
    logger.info("  Install with: pip install pypff (requires compilation)")


class EmailAnalyzer:
    """Analyzes email files and mailboxes"""
    
    def __init__(self, base_path=None):
        """
        Initialize email analyzer
        
        Args:
            base_path: Root path to search for email files
        
        Raises:
            FileSystemError: If base_path doesn't exist
        """
        self.base_path = Path(base_path) if base_path else Path.home()
        
        if not self.base_path.exists():
            raise FileSystemError(
                f"Base path does not exist: {self.base_path}",
                {'path': str(self.base_path)}
            )
        
        self.emails = []
        self.contacts = set()
        self.attachments = []
        self.domains = defaultdict(int)
        self.email_threads = {}
        
        logger.info(f"EmailAnalyzer initialized with base path: {self.base_path}")
    
    @handle_filesystem_errors
    def find_email_files(self):
        """
        Find all email files in base path
        
        Returns:
            dict: Dictionary mapping file types to lists of paths
        
        Raises:
            FileSystemError: If directory scanning fails
        """
        logger.info("Searching for email files...")
        
        try:
            email_files = {
                'pst': list(self.base_path.rglob('*.pst')),
                'ost': list(self.base_path.rglob('*.ost')),
                'mbox': list(self.base_path.rglob('*.mbox')),
                'eml': list(self.base_path.rglob('*.eml')),
                'msg': list(self.base_path.rglob('*.msg'))
            }
            
            total = sum(len(files) for files in email_files.values())
            logger.info(f"Found {total} email files:")
            
            for file_type, files in email_files.items():
                if files:
                    logger.info(f"  {file_type.upper()}: {len(files)}")
            
            return email_files
        
        except Exception as e:
            logger.error(f"Error finding email files: {e}")
            raise FileSystemError(
                f"Failed to search for email files: {str(e)}",
                {'base_path': str(self.base_path)}
            )
    
    def analyze_all(self, progress_callback=None):
        """
        Analyze all found email files
        
        Args:
            progress_callback: Optional callback(value, message)
        
        Raises:
            EmailAnalysisError: If analysis fails
        """
        # Create multi-step progress tracker
        tracker = MultiStepProgressTracker(
            progress_callback,
            [
                ("Finding Files", 10),
                ("Analyzing PST/OST", 30),
                ("Analyzing MBOX", 20),
                ("Analyzing EML", 20),
                ("Processing Metadata", 20)
            ]
        )
        
        tracker.start()
        
        try:
            # Step 1: Find files
            tracker.start_step("Finding Files")
            email_files = self.find_email_files()
            total_files = sum(len(files) for files in email_files.values())
            
            if total_files == 0:
                logger.warning("No email files found")
                tracker.complete("No email files found")
                return
            
            tracker.complete_step()
            
            # Step 2: Analyze PST/OST files
            tracker.start_step("Analyzing PST/OST")
            pst_ost_files = email_files['pst'] + email_files['ost']
            
            if pst_ost_files:
                for idx, pst_file in enumerate(pst_ost_files):
                    progress = int((idx / len(pst_ost_files)) * 100)
                    tracker.update_substep(progress, f"Analyzing {pst_file.name}")
                    self._analyze_pst(pst_file)
            
            tracker.complete_step()
            
            # Step 3: Analyze MBOX files
            tracker.start_step("Analyzing MBOX")
            
            if email_files['mbox']:
                for idx, mbox_file in enumerate(email_files['mbox']):
                    progress = int((idx / len(email_files['mbox'])) * 100)
                    tracker.update_substep(progress, f"Analyzing {mbox_file.name}")
                    self._analyze_mbox(mbox_file)
            
            tracker.complete_step()
            
            # Step 4: Analyze EML files
            tracker.start_step("Analyzing EML")
            
            if email_files['eml']:
                for idx, eml_file in enumerate(email_files['eml']):
                    progress = int((idx / len(email_files['eml'])) * 100)
                    tracker.update_substep(progress, f"Analyzing {eml_file.name}")
                    self._analyze_eml(eml_file)
            
            tracker.complete_step()
            
            # Step 5: Extract metadata
            tracker.start_step("Processing Metadata")
            tracker.update_substep(33, "Extracting domains...")
            self._extract_domains()
            
            tracker.update_substep(66, "Building email threads...")
            self._build_threads()
            
            tracker.complete_step()
            
            # Log summary
            logger.info(f"✓ Email analysis complete:")
            logger.info(f"  Total emails: {len(self.emails)}")
            logger.info(f"  Unique contacts: {len(self.contacts)}")
            logger.info(f"  Attachments: {len(self.attachments)}")
            logger.info(f"  Email threads: {len(self.email_threads)}")
            logger.info(f"  Domains: {len(self.domains)}")
            
            tracker.complete(
                f"Analysis complete! {len(self.emails)} emails, "
                f"{len(self.contacts)} contacts"
            )
        
        except Exception as e:
            logger.error(f"Email analysis failed: {e}")
            log_error_report(e, context={
                'base_path': str(self.base_path),
                'emails_processed': len(self.emails)
            })
            raise EmailAnalysisError(
                f"Failed to analyze emails: {str(e)}",
                {'base_path': str(self.base_path)}
            )
    
    def _analyze_pst(self, pst_path):
        """
        Analyze Outlook PST/OST file
        
        Args:
            pst_path: Path to PST/OST file
        """
        # Check if pypff is available
        if not is_available('pypff'):
            logger.warning(f"Cannot analyze {pst_path.name} - pypff not installed")
            return
        
        try:
            logger.info(f"Analyzing PST/OST: {pst_path.name}")
            
            pst = pypff.file()
            pst.open(str(pst_path))
            
            root = pst.get_root_folder()
            self._process_pst_folder(root, pst_path.name)
            
            pst.close()
            
            logger.info(f"✓ Completed PST/OST analysis: {pst_path.name}")
        
        except Exception as e:
            logger.error(f"Error analyzing PST {pst_path.name}: {e}")
            # Don't raise - continue with other files
    
    def _process_pst_folder(self, folder, source_file, folder_path=""):
        """
        Recursively process PST folder
        
        Args:
            folder: pypff folder object
            source_file: Source PST file name
            folder_path: Current folder path in hierarchy
        """
        try:
            folder_name = folder.get_name()
            current_path = f"{folder_path}/{folder_name}" if folder_path else folder_name
            
            # Process messages in this folder
            for i in range(folder.get_number_of_sub_messages()):
                try:
                    message = folder.get_sub_message(i)
                    self._process_pst_message(message, source_file, current_path)
                except Exception as e:
                    logger.debug(f"Error processing message {i} in {current_path}: {e}")
                    continue
            
            # Recurse into subfolders
            for i in range(folder.get_number_of_sub_folders()):
                try:
                    sub_folder = folder.get_sub_folder(i)
                    self._process_pst_folder(sub_folder, source_file, current_path)
                except Exception as e:
                    logger.debug(f"Error processing subfolder {i} in {current_path}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error processing PST folder {folder_path}: {e}")
    
    def _process_pst_message(self, message, source_file, folder_path):
        """
        Process a single PST message
        
        Args:
            message: pypff message object
            source_file: Source file name
            folder_path: Folder path
        """
        try:
            # Extract basic info
            subject = message.get_subject() or "(No Subject)"
            sender = message.get_sender_name() or ""
            sender_email = message.get_sender_email_address() or ""
            
            # Get timestamps
            try:
                delivery_time = message.get_delivery_time()
            except:
                delivery_time = None
            
            try:
                client_submit_time = message.get_client_submit_time()
            except:
                client_submit_time = None
            
            # Get body
            try:
                body_plain = message.get_plain_text_body() or ""
            except:
                body_plain = ""
            
            try:
                body_html = message.get_html_body() or ""
            except:
                body_html = ""
            
            # Get recipients
            recipients = []
            try:
                for i in range(message.get_number_of_recipients()):
                    recipient = message.get_recipient(i)
                    recipients.append({
                        'email': recipient.get_email_address() or "",
                        'name': recipient.get_name() or "",
                        'type': 'to'  # Could be 'to', 'cc', 'bcc'
                    })
            except:
                pass
            
            # Get attachments
            attachments = []
            try:
                for i in range(message.get_number_of_attachments()):
                    attachment = message.get_attachment(i)
                    self.attachments.append({
                        'email_subject': subject,
                        'filename': attachment.get_name() or f"attachment_{i}",
                        'size': attachment.get_size(),
                        'source': source_file,
                        'folder': folder_path
                    })
                    attachments.append({
                        'filename': attachment.get_name() or f"attachment_{i}",
                        'size': attachment.get_size(),
                        'type': 'file'
                    })
            except:
                pass
            
            # Extract Message-ID for threading
            message_id = None
            try:
                transport_headers = message.get_transport_headers()
                if transport_headers:
                    match = re.search(r'Message-ID:\s*<([^>]+)>', transport_headers, re.IGNORECASE)
                    message_id = match.group(1) if match else None
            except:
                pass
            
            # Store email
            email_entry = {
                'source': source_file,
                'source_type': 'pst',
                'folder': folder_path,
                'subject': subject,
                'sender_name': sender,
                'sender_email': sender_email,
                'recipients': recipients,
                'delivery_time': delivery_time,
                'submit_time': client_submit_time,
                'body_plain': body_plain[:500],  # Truncate for storage
                'body_html': body_html[:500],
                'has_attachments': len(attachments) > 0,
                'attachment_count': len(attachments),
                'attachments': attachments,
                'message_id': message_id,
                'size': message.get_size() if hasattr(message, 'get_size') else 0
            }
            
            self.emails.append(email_entry)
            
            # Add contacts
            if sender_email:
                self.contacts.add(sender_email.lower())
            for recipient in recipients:
                if recipient['email']:
                    self.contacts.add(recipient['email'].lower())
        
        except Exception as e:
            logger.debug(f"Error processing PST message: {e}")
    
    def _analyze_mbox(self, mbox_path):
        """
        Analyze MBOX file (Thunderbird, Mac Mail)
        
        Args:
            mbox_path: Path to MBOX file
        """
        try:
            logger.info(f"Analyzing MBOX: {mbox_path.name}")
            
            mbox = mailbox.mbox(str(mbox_path))
            
            for idx, message in enumerate(mbox):
                try:
                    self._process_email_message(message, mbox_path.name, 'mbox')
                except Exception as e:
                    logger.debug(f"Error processing MBOX message {idx}: {e}")
                    continue
            
            mbox.close()
            
            logger.info(f"✓ Completed MBOX analysis: {mbox_path.name}")
        
        except Exception as e:
            logger.error(f"Error analyzing MBOX {mbox_path.name}: {e}")
    
    def _analyze_eml(self, eml_path):
        """
        Analyze EML file
        
        Args:
            eml_path: Path to EML file
        """
        try:
            logger.debug(f"Analyzing EML: {eml_path.name}")
            
            with open(eml_path, 'rb') as f:
                message = email.message_from_binary_file(f)
            
            self._process_email_message(message, eml_path.name, 'eml')
        
        except Exception as e:
            logger.debug(f"Error analyzing EML {eml_path.name}: {e}")
    
    def _process_email_message(self, message, source_file, source_type):
        """
        Process Python email.message.Message object
        
        Args:
            message: email.message.Message object
            source_file: Source file name
            source_type: Type of source ('mbox', 'eml', etc.)
        """
        try:
            # Extract headers
            subject = message.get('Subject', '(No Subject)')
            sender = message.get('From', '')
            to = message.get('To', '')
            cc = message.get('Cc', '')
            date_str = message.get('Date', '')
            message_id = message.get('Message-ID', '')
            in_reply_to = message.get('In-Reply-To', '')
            
            # Parse date
            try:
                from email.utils import parsedate_to_datetime
                date = parsedate_to_datetime(date_str)
            except:
                date = None
            
            # Extract body
            body_plain = ""
            body_html = ""
            
            if message.is_multipart():
                for part in message.walk():
                    content_type = part.get_content_type()
                    
                    if content_type == 'text/plain':
                        try:
                            body_plain = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        except:
                            pass
                    elif content_type == 'text/html':
                        try:
                            body_html = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        except:
                            pass
            else:
                try:
                    body_plain = message.get_payload(decode=True).decode('utf-8', errors='ignore')
                except:
                    pass
            
            # Extract attachments
            attachments = []
            if message.is_multipart():
                for part in message.walk():
                    if part.get_content_disposition() == 'attachment':
                        filename = part.get_filename()
                        if filename:
                            payload = part.get_payload(decode=True) or b''
                            attachments.append({
                                'filename': filename,
                                'size': len(payload),
                                'type': 'file'
                            })
                            
                            self.attachments.append({
                                'email_subject': subject,
                                'filename': filename,
                                'size': len(payload),
                                'source': source_file,
                                'folder': ''
                            })
            
            # Parse recipients
            recipients = []
            for recipient_str in [to, cc]:
                if recipient_str:
                    # Simple email extraction
                    emails = re.findall(r'[\w\.-]+@[\w\.-]+', recipient_str)
                    for email_addr in emails:
                        recipients.append({
                            'email': email_addr,
                            'name': '',
                            'type': 'to' if recipient_str == to else 'cc'
                        })
            
            # Extract sender email
            sender_email = ""
            if sender:
                match = re.search(r'[\w\.-]+@[\w\.-]+', sender)
                if match:
                    sender_email = match.group(0)
            
            # Store email
            email_entry = {
                'source': source_file,
                'source_type': source_type,
                'folder': '',
                'subject': subject,
                'sender_name': sender,
                'sender_email': sender_email,
                'recipients': recipients,
                'delivery_time': date,
                'submit_time': date,
                'body_plain': body_plain[:500],
                'body_html': body_html[:500],
                'has_attachments': len(attachments) > 0,
                'attachment_count': len(attachments),
                'attachments': attachments,
                'message_id': message_id.strip('<>'),
                'in_reply_to': in_reply_to.strip('<>'),
                'size': len(str(message))
            }
            
            self.emails.append(email_entry)
            
            # Add contacts
            if sender_email:
                self.contacts.add(sender_email.lower())
            for recipient in recipients:
                if recipient['email']:
                    self.contacts.add(recipient['email'].lower())
        
        except Exception as e:
            logger.debug(f"Error processing email message: {e}")
    
    def _extract_domains(self):
        """Extract and count email domains"""
        logger.info("Extracting email domains...")
        
        try:
            for email_entry in self.emails:
                # Extract domain from sender
                sender_email = email_entry.get('sender_email', '')
                if sender_email and '@' in sender_email:
                    domain = sender_email.split('@')[1].lower()
                    self.domains[domain] += 1
                
                # Extract domains from recipients
                for recipient in email_entry.get('recipients', []):
                    recipient_email = recipient.get('email', '')
                    if recipient_email and '@' in recipient_email:
                        domain = recipient_email.split('@')[1].lower()
                        self.domains[domain] += 1
            
            logger.info(f"✓ Extracted {len(self.domains)} unique domains")
        
        except Exception as e:
            logger.error(f"Error extracting domains: {e}")
    
    def _build_threads(self):
        """Build email threads based on Message-ID and In-Reply-To"""
        logger.info("Building email threads...")
        
        try:
            # Create message ID index
            message_index = {}
            for email_entry in self.emails:
                msg_id = email_entry.get('message_id')
                if msg_id:
                    message_index[msg_id] = email_entry
            
            # Build threads
            for email_entry in self.emails:
                in_reply_to = email_entry.get('in_reply_to')
                if in_reply_to and in_reply_to in message_index:
                    # This email is a reply
                    parent = message_index[in_reply_to]
                    
                    # Get or create thread
                    parent_msg_id = parent.get('message_id')
                    if parent_msg_id not in self.email_threads:
                        self.email_threads[parent_msg_id] = {
                            'root': parent,
                            'replies': []
                        }
                    
                    self.email_threads[parent_msg_id]['replies'].append(email_entry)
            
            logger.info(f"✓ Built {len(self.email_threads)} email threads")
        
        except Exception as e:
            logger.error(f"Error building threads: {e}")
    
    def export_to_json(self, output_path):
        """
        Export email analysis to JSON
        
        Args:
            output_path: Path to output JSON file
        
        Raises:
            EmailAnalysisError: If export fails
        """
        import json
        
        try:
            logger.info(f"Exporting email analysis to {output_path}")
            
            export_data = {
                'emails': self.emails,
                'contacts': list(self.contacts),
                'attachments': self.attachments,
                'domains': dict(self.domains),
                'threads': len(self.email_threads),
                'summary': {
                    'total_emails': len(self.emails),
                    'total_contacts': len(self.contacts),
                    'total_attachments': len(self.attachments),
                    'total_domains': len(self.domains)
                }
            }
            
            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            logger.info(f"✓ Email analysis exported to {output_path}")
        
        except Exception as e:
            logger.error(f"Export failed: {e}")
            raise EmailAnalysisError(
                f"Failed to export email analysis: {str(e)}",
                {'output_path': str(output_path)}
            )