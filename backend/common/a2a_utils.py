"""
Utility functions for A2A (Agent-to-Agent) protocol conversions.

This module provides conversion functions between A2A Part types and Google Gen AI Part types,
enabling seamless interoperability between the two systems.
"""

from a2a.types import (
    FilePart,
    FileWithBytes,
    FileWithUri,
    Part,
    TextPart,
    AgentSkill,
)
from google.genai import types
import inspect
import re
from typing import List


def convert_a2a_part_to_genai(part: Part) -> types.Part:
    """Convert a single A2A Part type into a Google Gen AI Part type.

    Args:
        part: The A2A Part to convert

    Returns:
        The equivalent Google Gen AI Part

    Raises:
        ValueError: If the part type is not supported
    """
    part = part.root
    if isinstance(part, TextPart):
        return types.Part(text=part.text)
    if isinstance(part, FilePart):
        if isinstance(part.file, FileWithUri):
            return types.Part(
                file_data=types.FileData(
                    file_uri=part.file.uri, mime_type=part.file.mime_type
                )
            )
        if isinstance(part.file, FileWithBytes):
            return types.Part(
                inline_data=types.Blob(
                    data=part.file.bytes, mime_type=part.file.mime_type
                )
            )
        raise ValueError(f'Unsupported file type: {type(part.file)}')
    raise ValueError(f'Unsupported part type: {type(part)}')


def convert_genai_part_to_a2a(part: types.Part) -> Part:
    """Convert a single Google Gen AI Part type into an A2A Part type.

    Args:
        part: The Google Gen AI Part to convert

    Returns:
        The equivalent A2A Part

    Raises:
        ValueError: If the part type is not supported
    """
    if part.text:
        return TextPart(text=part.text)
    if part.file_data:
        return FilePart(
            file=FileWithUri(
                uri=part.file_data.file_uri,
                mime_type=part.file_data.mime_type,
            )
        )
    if part.inline_data:
        return Part(
            root=FilePart(
                file=FileWithBytes(
                    bytes=part.inline_data.data,
                    mime_type=part.inline_data.mime_type,
                )
            )
        )
    raise ValueError(f'Unsupported part type: {part}')


def generate_skills_from_mcp_instance(mcp_instance) -> List[AgentSkill]:
    """
    Inspects a FastMCP instance and generates AgentSkill objects from its registered tools' docstrings.
    
    Args:
        mcp_instance: The FastMCP instance (e.g., the 'mcp' variable from retail_mcp.py)
        
    Returns:
        List of AgentSkill objects parsed from the MCP tools
    """
    skills = []
    
    # Get the module where the mcp instance is defined
    mcp_module = inspect.getmodule(mcp_instance)
    
    if not mcp_module:
        print("[WARNING] Could not find module for MCP instance")
        return skills
    
    # Get all functions from the module
    for name, obj in inspect.getmembers(mcp_module, predicate=inspect.isfunction):
        if name.startswith('_'):
            continue  # Skip private functions
        
        # Skip helper functions (formatters, utilities, etc.)
        if name.startswith('format_') or name in ['shutdown_event', 'get_bank_response']:
            continue
        
        # Get the docstring
        docstring = inspect.getdoc(obj)
        if not docstring or "@skill.description" not in docstring:
            continue
        
        try:
            # Use regex to parse our custom tags
            # Updated regex to handle the new docstring format with :param
            description_match = re.search(r"@skill.description\n(.*?)(?=\n@skill|\n\n:param|\Z)", docstring, re.DOTALL)
            examples_match = re.search(r"@skill.examples\n(.*?)(?=\n@skill|\Z)", docstring, re.DOTALL)
            tags_match = re.search(r"@skill.tags\n(.*?)(?=\n@skill|\n\n:param|\Z)", docstring, re.DOTALL)
            
            description = description_match.group(1).strip() if description_match else "No description provided."
            
            # Parse examples, stripping the leading '-' and whitespace
            examples_raw = examples_match.group(1).strip() if examples_match else ""
            examples = [ex.strip().lstrip('- ') for ex in examples_raw.split('\n') if ex.strip()]
            
            # Parse tags
            tags_raw = tags_match.group(1).strip() if tags_match else ""
            tags = [tag.strip().lstrip('- ') for tag in tags_raw.split('\n') if tag.strip()]
            
            # Create the AgentSkill object
            skill = AgentSkill(
                id=name,
                name=name,
                description=description,
                examples=examples,
                tags=tags,
            )
            skills.append(skill)
            print(f"[INFO] Successfully parsed skill: {name}")
        except Exception as e:
            print(f"[WARNING] Could not parse docstring for skill '{name}'. Error: {e}")
    
    return skills
